//! Binário executável do Sidecar MCP / Rust+CUDA (`squad-gpu-lab-mcp.exe`).
//!
//! Modos de operação:
//! - `--jsonrpc <payload>`: executa 1 chamada JSON-RPC e imprime na `stdout` (compatibilidade CLI).
//! - `--serve-stdio`: loop persistente JSON-RPC 2.0 sobre `stdin`/`stdout` mantendo `CudaContext` quente.
//! - `--serve-tcp <host:port>`: loop persistente JSON-RPC 2.0 sobre Loopback TCP Keep-Alive (`~194 µs/call`).

use mcp_server::LabMcpServer;
use std::env;
use std::io::{self, BufRead, BufReader, Write};
use std::net::TcpListener;

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut srv = LabMcpServer::new();

    if args.len() >= 3 && args[1] == "--jsonrpc" {
        let resp = srv.handle_jsonrpc_line(&args[2]);
        println!("{}", resp);
        return;
    }

    if args.len() >= 3 && args[1] == "--serve-tcp" {
        let addr = &args[2];
        let listener = TcpListener::bind(addr).expect("bind TCP loopback");
        let bound = listener.local_addr().expect("local_addr");
        println!("READY_TCP {}", bound);
        let _ = io::stdout().flush();

        for stream in listener.incoming().flatten() {
            let _ = stream.set_nodelay(true);
            let mut reader = BufReader::new(stream.try_clone().expect("clone stream"));
            let mut writer = stream;
            let mut line = String::new();
            while reader.read_line(&mut line).unwrap_or(0) > 0 {
                let trimmed = line.trim();
                if trimmed == "QUIT" {
                    return;
                }
                if !trimmed.is_empty() {
                    let resp = srv.handle_jsonrpc_line(trimmed);
                    let _ = writer.write_all(resp.as_bytes());
                    let _ = writer.write_all(b"\n");
                    let _ = writer.flush();
                }
                line.clear();
            }
        }
        return;
    }

    // Default / --serve-stdio: persistent stdio loop
    let stdin = io::stdin();
    let mut stdout = io::stdout();
    for line in stdin.lock().lines().map_while(Result::ok) {
        let trimmed = line.trim();
        if trimmed == "QUIT" {
            break;
        }
        if !trimmed.is_empty() {
            let resp = srv.handle_jsonrpc_line(trimmed);
            let _ = writeln!(stdout, "{}", resp);
            let _ = stdout.flush();
        }
    }
}
