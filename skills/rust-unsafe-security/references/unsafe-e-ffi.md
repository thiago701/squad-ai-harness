# `unsafe` e FFI em Rust (edição 2024, rustc 1.99)

> Autoral (Squad AI). O código das §3–§5 é o **arquivo real** que compilou, passou no `clippy -D warnings` com os lints abaixo e foi executado sob **Miri**
> (`cargo +nightly miri test`: 4 testes ok + 1 ignorado — o FFI para libc, que o Miri não executa). As mensagens de UB (Miri/ASAN) e de lint são **saídas reais**
> capturadas em rustc 1.99.0 / nightly; os números `allocNNN` e endereços variam a cada execução.
> Fonte conceitual: *Rust Reference — Behavior considered undefined*, *The Rustonomicon*, documentação do Miri e do Clippy (reescrito, sem cópia).

## 1. O que é UB (lista curta que importa)

Comportamento indefinido em Rust (resumo — a lista completa está na *Reference*): acesso fora dos limites/pendente (*dangling*)/desalinhado/nulo; **data race**;
violar as regras de aliasing (`&mut` exclusivo; `&` imutável); produzir valor inválido (`bool` ≠ 0/1, `char` inválido, enum com discriminante inexistente, `&`/`Box` nulo/pendente,
memória não inicializada lida como inteiro; `str` não-UTF-8 é UB de **biblioteca** — `from_utf8_unchecked` —, não da linguagem); chamar função com ABI/assinatura errada; desenrolar (*unwind*) por fronteira que não permite.
UB **não** é "pode dar erro": o compilador assume que ele não ocorre e otimiza com base nisso — o programa pode "funcionar" em debug e quebrar em release.

Não é UB (mas é bug): vazamento de memória (`mem::forget`), deadlock, overflow aritmético (pânico em debug / *wrapping* em release, definido), pânico, `exit`.

## 2. Lints obrigatórios (`Cargo.toml`)

```toml
[lints.rust]
unsafe_op_in_unsafe_fn = "deny"     # edição 2024: já é warn; negue — cada operação unsafe tem seu bloco
# unsafe_code = "forbid"            # use em TODO crate que não precisa de unsafe

[lints.clippy]
undocumented_unsafe_blocks = "deny" # todo `unsafe {}` exige comentário `// SAFETY:`
missing_safety_doc = "deny"         # toda `unsafe fn` pública exige seção `# Safety`
multiple_unsafe_ops_per_block = "warn"
```

Saída real do `cargo clippy` num arquivo que viola tudo:

```text
error[E0133]: dereference of raw pointer is unsafe and requires unsafe block
 --> src/lib.rs:2:5                     (unsafe fn ler(p) { *p }  — com unsafe_op_in_unsafe_fn = deny)
error: unsafe function's docs are missing a `# Safety` section
 --> src/lib.rs:1:1
error: this public function might dereference a raw pointer but is not marked `unsafe`
  --> src/lib.rs:11:15                  (fn dois(p: *const u8, q: *const u8) { unsafe { *p + *q } })
error: unsafe block missing a safety comment
  --> src/lib.rs:11:5
   = help: consider adding a safety comment on the preceding line
warning: this `unsafe` block contains 2 unsafe operations, expected only one
  --> src/lib.rs:11:5
```

Leitura: o lint `not_unsafe_ptr_arg_deref` (padrão do Clippy) pega a **função segura que desreferencia ponteiro** — o erro de soundness mais comum. A correção é torná-la `unsafe fn`
com `# Safety`, ou receber uma referência/slice (`&u8`, `&[u8]`) em vez de ponteiro cru.

## 3. Estruturas com invariante: `Stack<T, N>` (código verificado)

Invariante (escrita no doc do tipo): `len <= N` e `buf[..len]` está inicializado. Campos **privados**; todo método seguro preserva a invariante; `Drop` descarta cada elemento vivo uma vez.
Teste de vazamento/duplo free: o Miri acusa se o `Drop` estiver errado.

```rust
use std::mem::MaybeUninit;

/// Buffer de capacidade fixa na pilha: invariante `len <= N` e `buf[..len]` está inicializado.
pub struct Stack<T, const N: usize> {
    buf: [MaybeUninit<T>; N],
    len: usize,
}

impl<T, const N: usize> Stack<T, N> {
    #[must_use]
    pub fn new() -> Self {
        Self {
            buf: [const { MaybeUninit::uninit() }; N],
            len: 0,
        }
    }

    /// Devolve o valor se estiver cheia (sem pânico, sem alocação).
    pub fn push(&mut self, v: T) -> Result<(), T> {
        if self.len == N {
            return Err(v);
        }
        self.buf[self.len].write(v);
        self.len += 1;
        Ok(())
    }

    pub fn pop(&mut self) -> Option<T> {
        if self.len == 0 {
            return None;
        }
        self.len -= 1;
        // SAFETY: pela invariante, `buf[len]` (após o decremento) estava inicializado e
        // agora sai do intervalo vivo; `assume_init_read` o move para fora uma única vez.
        Some(unsafe { self.buf[self.len].assume_init_read() })
    }

    #[must_use]
    pub fn as_slice(&self) -> &[T] {
        // SAFETY: `buf[..len]` está inicializado (invariante) e `MaybeUninit<T>` tem o mesmo
        // layout de `T`; o empréstimo de `&self` impede mutação durante a vida do slice.
        unsafe { std::slice::from_raw_parts(self.buf.as_ptr().cast::<T>(), self.len) }
    }
}

impl<T, const N: usize> Default for Stack<T, N> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T, const N: usize> Drop for Stack<T, N> {
    fn drop(&mut self) {
        while self.pop().is_some() {} // descarta cada elemento vivo exatamente uma vez
    }
}

/// Divide um slice mutável em dois — reimplementação didática de `split_at_mut`.
///
/// # Panics
/// Se `mid > s.len()`.
pub fn split_two(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
    let len = s.len();
    assert!(mid <= len);
    let p = s.as_mut_ptr();
    // SAFETY: `mid <= len` (assert acima); a faixa [0, mid) está dentro da alocação e o `&mut`
    // de entrada garante exclusividade; esta faixa não se sobrepõe à da linha seguinte.
    let left = unsafe { std::slice::from_raw_parts_mut(p, mid) };
    // SAFETY: [mid, len) é disjunta de [0, mid) e está dentro da alocação original.
    let right = unsafe { std::slice::from_raw_parts_mut(p.wrapping_add(mid), len - mid) };
    (left, right)
}

// FFI (edição 2024): bloco `unsafe extern`; itens `safe` são chamáveis sem `unsafe`.
unsafe extern "C" {
    pub safe fn abs(x: i32) -> i32;
    pub unsafe fn strlen(s: *const std::ffi::c_char) -> usize;
}

/// Exporta um símbolo C. Em 2024 o atributo exige `unsafe(...)`.
#[unsafe(no_mangle)]
pub extern "C" fn squad_soma(a: i32, b: i32) -> i32 {
    a.wrapping_add(b)
}

/// Exportada para C: mede o comprimento em bytes de uma string C, sem deixar pânico escapar.
///
/// Devolve `0` em sucesso, `-1` para ponteiro nulo e `-2` se houve pânico interno.
///
/// # Safety
/// `s` deve ser nulo ou apontar para uma string C válida, terminada em NUL, viva durante a
/// chamada; `out` deve ser nulo ou apontar para um `usize` gravável e alinhado.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn squad_strlen(s: *const std::ffi::c_char, out: *mut usize) -> i32 {
    if s.is_null() || out.is_null() {
        return -1;
    }
    let r = std::panic::catch_unwind(|| {
        // SAFETY: `s` não é nulo e, pelo contrato (`# Safety`), aponta para string C válida e viva.
        unsafe { std::ffi::CStr::from_ptr(s) }.to_bytes().len()
    });
    match r {
        Ok(n) => {
            // SAFETY: `out` não é nulo e, pelo contrato, é gravável e alinhado.
            unsafe { out.write(n) };
            0
        }
        Err(_) => -2,
    }
}

#[must_use]
pub fn comprimento_c(s: &std::ffi::CStr) -> usize {
    // SAFETY: `CStr` garante ponteiro válido, terminado em NUL e vivo durante a chamada.
    unsafe { strlen(s.as_ptr()) }
}

/// `Send` manual: só porque o ponteiro é dono exclusivo do dado e nunca é compartilhado.
pub struct Dono(*mut u32);
// SAFETY: `Dono` é o único dono do `u32` apontado; mover entre threads não cria aliasing.
unsafe impl Send for Dono {}

impl Dono {
    #[must_use]
    pub fn novo(v: u32) -> Self {
        Self(Box::into_raw(Box::new(v)))
    }
    #[must_use]
    pub fn valor(&self) -> u32 {
        // SAFETY: o ponteiro vem de `Box::into_raw` e permanece válido até o `Drop`.
        unsafe { *self.0 }
    }
}

impl Drop for Dono {
    fn drop(&mut self) {
        // SAFETY: ponteiro criado por `Box::into_raw` em `novo`; liberado exatamente uma vez aqui.
        drop(unsafe { Box::from_raw(self.0) });
    }
}
```

Testes que acompanham (rodam sob Miri sem erro, exceto o de libc que é `ignore` no Miri):

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CString;

    #[test]
    fn stack_basica() {
        let mut s: Stack<String, 2> = Stack::new();
        assert!(s.push("a".into()).is_ok());
        assert!(s.push("b".into()).is_ok());
        assert_eq!(s.push("c".into()), Err("c".to_string()));
        assert_eq!(s.as_slice(), ["a", "b"]);
        assert_eq!(s.pop().as_deref(), Some("b"));
    } // `Drop` libera o que sobrou: o Miri acusaria vazamento/duplo free

    #[test]
    fn split_e_ffi() {
        let mut v = [1, 2, 3, 4];
        let (a, b) = split_two(&mut v, 2);
        a[0] = 10;
        b[1] = 40;
        assert_eq!(v, [10, 2, 3, 40]);
        assert_eq!(squad_soma(2, 3), 5);
    }

    // O Miri não executa funções estrangeiras arbitrárias: teste FFI só fora dele.
    #[test]
    #[cfg_attr(miri, ignore)]
    fn ffi_libc() {
        assert_eq!(abs(-5), 5);
        assert_eq!(comprimento_c(&CString::new("olá").unwrap()), 4);
    }

    #[test]
    fn strlen_exportada_trata_nulos() {
        let c = CString::new("abc").unwrap();
        let mut n = 0usize;
        // SAFETY: ponteiros válidos e vivos nesta chamada (contrato de `squad_strlen`).
        assert_eq!(unsafe { squad_strlen(c.as_ptr(), &raw mut n) }, 0);
        assert_eq!(n, 3);
        // SAFETY: nulo é explicitamente aceito pelo contrato e devolve -1.
        assert_eq!(unsafe { squad_strlen(std::ptr::null(), &raw mut n) }, -1);
    }

    #[test]
    fn dono_send() {
        let d = Dono::novo(7);
        std::thread::spawn(move || assert_eq!(d.valor(), 7))
            .join()
            .unwrap();
    }
}
```

Pontos de design a copiar:

- `[const { MaybeUninit::uninit() }; N]` cria o array sem `T: Copy` (const blocks, estáveis desde 1.79).
- `assume_init_read` **move** o valor para fora; depois do decremento ele não está mais "vivo" (fora de `buf[..len]`).
- `split_two` usa `wrapping_add` + duas faixas **disjuntas** a partir de **um** `&mut` de entrada — mas em produção prefira `slice::split_at_mut`; o exemplo é didático e o comentário mostra a prova de disjunção.
- `Dono` mostra o par `Box::into_raw`/`Box::from_raw` (posse transferida e devolvida **uma** vez) e `unsafe impl Send` com justificativa de posse exclusiva.

## 4. Miri — o que ele detecta (saídas reais)

Execução: `rustup toolchain install nightly --component miri` → `cargo +nightly miri test` (ou `miri run`). Mais lento (ordem de grandeza ~10–100×, não medida aqui) e interpreta MIR: **não executa C por padrão** (FFI → `#[cfg_attr(miri, ignore)]`; existe o experimental `-Zmiri-native-lib`, que pode causar UB no próprio Miri), cobre só o que os testes exercitam.
Útil também: `MIRIFLAGS="-Zmiri-backtrace=full"`, `-Zmiri-ignore-leaks` (desligar checagem de vazamento), `-Zmiri-many-seeds` (várias semeaduras de agendamento para achar *races*).

Casos reproduzidos (programa mínimo com cada bug):

```text
# leitura além da alocação — p.add(5) em Vec de 3 bytes
error: Undefined Behavior: in-bounds pointer arithmetic failed: attempting to offset pointer by 5 bytes,
       but got alloc780 which is only 3 bytes from the end of the allocation

# uso após liberar
error: Undefined Behavior: memory access failed: alloc784 has been freed, so this pointer is dangling
help: alloc784 was allocated here:      (Box::new(42))
help: alloc784 was deallocated here:    (drop(Box::from_raw(p)))

# violação de aliasing — escrita por ponteiro cru invalidada por um `&mut` posterior
error: Undefined Behavior: attempting a write access using <1614> at alloc773[0x0], but that tag does not exist in the borrow stack for this location
help: <1614> was created by a SharedReadWrite retag ...  (let p = &raw mut x;)
help: <1614> was later invalidated at offsets [0x0..0x4] by a Unique retag   (let r = &mut x;)

# valor inválido
error: Undefined Behavior: constructing invalid value of type bool: encountered 0x03, but expected a boolean   (transmute::<u8, bool>(3))

# data race em static mut
error: Undefined Behavior: Data race detected between (1) non-atomic write on thread `main` and (2) non-atomic read on thread `unnamed-1`

# vazamento (mem::forget)
error: memory leaked: alloc802 (Rust heap, size: 16, align: 1), allocated here: ...
```

Como ler: a mensagem diz **qual** regra quebrou; os `help:` apontam onde a alocação/etiqueta foi **criada** e **invalidada** — vá ao segundo ponto (a invalidação) para achar a causa.
Aviso honesto: o modelo de aliasing (Stacked/Tree Borrows) ainda é experimental; um erro do Miri em código que você considera correto merece análise (pode ser limitação do modelo), mas **nunca** silencie sem entender.

## 5. AddressSanitizer (código com FFI ou muito `unsafe`)

```bash
# nightly + target explícito; use um diretório de build separado (as flags invalidam o cache)
# -Zbuild-std (precisa de `rustup component add rust-src --toolchain nightly`) é fortemente recomendado
# para ASAN/TSAN e estritamente necessário para MSan (Unstable Book); doctests exigem tratamento à parte.
RUSTFLAGS="-Zsanitizer=address" cargo +nightly run -Zbuild-std --target x86_64-unknown-linux-gnu
RUSTFLAGS="-Zsanitizer=address" cargo +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu
```

Saídas reais (resumidas — a pilha completa traz dezenas de quadros do runtime):

```text
==22108==ERROR: AddressSanitizer: heap-use-after-free on address 0x7b9ca51e0030 ...
READ of size 4 at 0x7b9ca51e0030 thread T0
    #0 ... in ub::main src/main.rs:14:37
0x7b9ca51e0030 is located 0 bytes inside of 4-byte region [0x7b9ca51e0030,0x7b9ca51e0034)
freed by thread T0 here: ...

==22116==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x7bf3befe0035 ...
READ of size 1 at 0x7bf3befe0035 thread T0
0x7bf3befe0035 is located 2 bytes after 3-byte region [0x7bf3befe0030,0x7bf3befe0033)
```

Miri × ASAN: Miri é mais **preciso** em semântica de Rust (aliasing, valores inválidos, *races*) mas só interpreta Rust; ASAN é **rápido** e vê também código C ligado (FFI), mas não conhece as regras de aliasing do Rust. Use os dois em código de FFI.
Outros sanitizers (`thread`, `memory`, `leak`) existem no nightly; **não** foram executados aqui. `loom` (modelo de concorrência exaustivo) e `cargo careful` são de terceiros e **não foram verificados**.

## 6. FFI — Rust chamando C (`unsafe extern`)

Já mostrado no código da §3: na edição 2024 o bloco é `unsafe extern "C" { … }`; cada item é `unsafe fn` por padrão, e **você** marca `safe fn` só quando o contrato da função C é provadamente
seguro para qualquer argumento (`abs(i32) -> i32`). `strlen` continua `unsafe` (exige ponteiro válido) e o *wrapper* seguro recebe `&CStr`, que **garante** NUL-terminado e validade.

Regras do wrapper seguro:

- Strings: `&CStr`/`CString` (nunca `&str` direto para C; `CString::new` falha se houver NUL interno — trate o `Result`). Texto vindo de C: `CStr::from_ptr(p).to_str()` (valida UTF-8) ou `to_string_lossy()`.
- Tipos: `#[repr(C)]` em structs/enums trocados; `std::ffi::{c_int, c_char, c_void, c_long…}` (ou `core::ffi`) em vez de `i32`/`i8` "de cabeça".
- Ponteiro nulo é valor normal vindo de C: `Option<&T>`/`Option<NonNull<T>>` têm o mesmo layout que o ponteiro (otimização de nicho) e dispensam `is_null` manual em assinaturas.
- Posse: documente **quem libera** e **com qual função**. Memória alocada pelo Rust se libera com Rust (`Box::from_raw`), a do C com `free`/função da lib — nunca cruzado.
- Erros: C devolve códigos/`errno`; converta para `enum` + `thiserror` na fronteira (→ **rust-pro**).
- Geração de *bindings*: `bindgen` (C→Rust) e `cbindgen` (Rust→C) são ferramentas **de terceiros, não verificadas aqui**; saída gerada é código a revisar, não confiável por padrão. Convenção: crate `foo-sys` (só `extern`) + crate `foo` (API segura).

## 7. FFI — C chamando Rust (`#[unsafe(no_mangle)] extern "C"`)

Pânico **não pode** atravessar `extern "C"`. Em 1.99 o runtime **aborta** o processo (comportamento verificado):

```rust
extern "C" fn cb() {
    panic!("falha dentro do callback");
}
fn main() { println!("antes"); cb(); println!("depois"); }
```

```text
antes
thread 'main' panicked at a.rs:2:5:
falha dentro do callback
thread 'main' panicked at .../core/src/panicking.rs:225:5:
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
Aborted   (exit code 134 / SIGABRT)
```

"Depois" nunca é impresso. Em biblioteca que C chama, **isso derruba o processo hospedeiro** — decida conscientemente: (a) converter pânico em código de erro com `catch_unwind` (padrão da `squad_strlen` na §3, devolve `-2`), ou (b) assumir o abort e documentar.
`extern "C-unwind"` permite *unwind* através da fronteira quando o outro lado também suporta (C++/Rust com ABI compatível); é uma escolha de ABI delicada, **não exercitada aqui** — leia a *Reference* antes de usar.

Checklist de função exportada: nome estável com `#[unsafe(no_mangle)]` (2024); `# Safety` descrevendo o que C deve garantir; checar nulos **antes** de desreferenciar; `catch_unwind` (ou abort documentado);
nunca devolver `&`/`String`/`Vec` — só tipos `repr(C)`/escalares e ponteiros opacos (`Box::into_raw` + função `*_free` correspondente); `panic = "abort"` no perfil é alternativa simples se a biblioteca inteira aceita abortar.

## 8. `Send`/`Sync` manuais, `static mut` e ambiente (edição 2024)

- `unsafe impl Send for Tipo {}` só com argumento de posse exclusiva ou sincronização real (ver `Dono`); `Sync` exige que `&Tipo` seja seguro em várias threads. Prefira compor tipos que já são `Send`/`Sync`.
- `static mut`: referência a ele é erro por padrão na 2024 (`static_mut_refs`). Alternativas, em ordem: `AtomicXxx`, `Mutex`/`LazyLock<Mutex<T>>`, `OnceLock<T>`; só em último caso `&raw mut`/`&raw const` dentro de `unsafe` com prova de ausência de *race* (Miri acusa — §4).
- `std::env::set_var`/`remove_var` são `unsafe` (E0133): mutar o ambiente com outras threads lendo é UB em Unix. Leia configuração uma vez na inicialização e passe como parâmetro.
- Reinterpretar bytes: prefira `u32::from_le_bytes`, `bytemuck::cast_slice`/`zerocopy` (terceiros, não verificados aqui) a `transmute`; `transmute` só com tipos de layout garantido (`repr(C)`/`repr(transparent)`/primitivos) e comprovando todas as combinações de bits válidas.

## 9. Receita de revisão (copiar para o PR)

```text
[ ] cargo clippy --all-targets -- -D warnings            (lints de unsafe da §2 ativos)
[ ] cargo test                                            (verde)
[ ] cargo +nightly miri test                              (verde; FFI com cfg_attr(miri, ignore))
[ ] ASAN em FFI/unsafe pesado                             (RUSTFLAGS="-Zsanitizer=address" … --target <triple>)
[ ] cada `unsafe {}` com `// SAFETY:` que responde às 7 perguntas da SKILL
[ ] `unsafe fn`/`unsafe trait` públicos com `# Safety`
[ ] nenhuma função SEGURA pode causar UB (soundness): tente quebrar com argumentos hostis
[ ] fronteira FFI: nulos, posse, pânico (catch_unwind/abort), repr(C)
```
