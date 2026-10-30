// Command squad-harness is the unified static binary for SquadAI Harness v0.8.0 (Go 1.24.3, CGO_ENABLED=0).
// It consolidates the pipeline DAG runner, delivery gates, Layer 0 CognitiveHarness,
// SEKG + GraphRAG engine, 25-specialist JEV tribunal, Sonar-First analyzer, hot-path hooks,
// 8D Intelligent Task Scheduler + IMO, and native MCP stdio server.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strings"
	"time"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/graphrag"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/harness"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/sekg"
	"github.com/thiago701/squad-ai-harness/internal/compute"
	"github.com/thiago701/squad-ai-harness/internal/dag"
	"github.com/thiago701/squad-ai-harness/internal/gates"
	"github.com/thiago701/squad-ai-harness/internal/git"
	"github.com/thiago701/squad-ai-harness/internal/hooks"
	"github.com/thiago701/squad-ai-harness/internal/installer"
	"github.com/thiago701/squad-ai-harness/internal/jev"
	"github.com/thiago701/squad-ai-harness/internal/mcp"
	"github.com/thiago701/squad-ai-harness/internal/runtime/jobobject"
	"github.com/thiago701/squad-ai-harness/internal/ui"
	"github.com/thiago701/squad-ai-harness/pkg/contracts"
)

func main() {
	// Enforce 256 MiB GOMEMLIMIT ceiling on the Go runtime heap
	debug.SetMemoryLimit(256 * 1024 * 1024)
	os.Exit(runCLI(os.Args[1:]))
}

func resolveRepoRoot() string {
	if envRoot := os.Getenv("SQUAD_HARNESS_RAIZ"); envRoot != "" {
		return envRoot
	}
	if envRoot := os.Getenv("HARNESS_REPO"); envRoot != "" {
		return envRoot
	}
	cwd, err := os.Getwd()
	if err != nil {
		return "."
	}
	return cwd
}

func runCLI(args []string) int {
	if len(args) == 0 || args[0] == "help" || args[0] == "--help" || args[0] == "-h" {
		printUsage()
		return 0
	}

	rootDir := resolveRepoRoot()
	cmd := args[0]

	switch cmd {
	case "version", "--version", "-v":
		mem, _ := jobobject.ProbeSystemMemory()
		out := map[string]any{
			"product":       contracts.ProductName,
			"technical_id":  contracts.TechnicalName,
			"version":       contracts.Version,
			"full_identity": contracts.FullIdentity,
			"go_version":    runtime.Version(),
			"os_arch":       runtime.GOOS + "/" + runtime.GOARCH,
			"cpu_cores":     runtime.NumCPU(),
			"avail_ram_mb":  mem.AvailPhysMB,
			"total_ram_mb":  mem.TotalPhysMB,
		}
		printJSON(out)
		return 0

	case "hook":
		if len(args) < 2 {
			fmt.Fprintln(os.Stderr, "uso: squad-harness hook <pre-tool|post-tool|stop>")
			return 2
		}
		var code int
		var msg string
		switch args[1] {
		case "pre-tool":
			code, msg = hooks.PreToolUse(rootDir, os.Stdin)
		case "post-tool":
			code, msg = hooks.PostToolUse(rootDir, os.Stdin)
		case "stop":
			code, msg = hooks.StopHook(rootDir, os.Stdin)
		default:
			fmt.Fprintf(os.Stderr, "hook desconhecido: %s\n", args[1])
			return 2
		}
		if msg != "" {
			fmt.Println(msg)
		}
		return code

	case "preflight":
		query := "auditoria de arquitetura e seguranca"
		if len(args) > 1 {
			query = args[1]
		}
		eng, err := harness.NewEngine(rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro ao inicializar engine cognitiva: %v\n", err)
			return 1
		}
		res := eng.RunPreflight(query, nil)
		printJSON(res)
		return 0

	case "sekg":
		eng, err := harness.NewEngine(rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro no SEKG: %v\n", err)
			return 1
		}
		sub := "status"
		if len(args) > 1 {
			sub = args[1]
		}
		switch sub {
		case "index":
			dbPath := filepath.Join(rootDir, ".squad-harness", "sekg.db")
			digest, err := eng.Graph().SaveAtomic(dbPath)
			if err != nil {
				fmt.Fprintf(os.Stderr, "erro ao salvar SEKG: %v\n", err)
				return 1
			}
			printJSON(map[string]any{
				"db_path":     dbPath,
				"sha256":      digest,
				"nodes":       len(eng.Graph().Nodes),
				"edges":       len(eng.Graph().Edges),
				"communities": len(eng.Graph().Communities),
			})
		case "query":
			q := "arquitetura geral"
			mode := ""
			if len(args) > 2 {
				q = args[2]
			}
			if len(args) > 3 {
				mode = args[3]
			}
			rag := graphrag.NewEngine(eng.Graph())
			resp := rag.Search(graphrag.QueryRequest{
				Query: q,
				Mode:  graphrag.SearchMode(mode),
				TopK:  5,
			})
			printJSON(resp)
		case "impact":
			target := "gates"
			if len(args) > 2 {
				target = args[2]
			}
			printJSON(eng.Graph().AnalyzeImpact([]string{target}))
		default:
			printJSON(map[string]any{
				"nodes":       len(eng.Graph().Nodes),
				"edges":       len(eng.Graph().Edges),
				"communities": len(eng.Graph().Communities),
			})
		}
		return 0

	case "gate":
		return runUnifiedGateDAG(rootDir)

	case "sync":
		plan, err := git.BuildPlan(context.Background(), rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro no git-sync: %v\n", err)
			return 1
		}
		printJSON(plan)
		return 0

	case "jev":
		diff := ""
		if len(args) > 1 {
			diff = args[1]
		}
		verdict := jev.EvaluateTribunal(jev.ReviewInput{DiffContent: diff})
		printJSON(verdict)
		if verdict.GateState != contracts.GatePass {
			return 1
		}
		return 0

	case "compute":
		prof := compute.DetectWorkstation()
		cb := compute.NewCircuitBreaker()
		decC0 := compute.RouteWorkload(prof, cb, "jev.review", 1, 64, false)
		decC1 := compute.RouteWorkload(prof, cb, "embed.query", 1, 64, false)
		decC2 := compute.RouteWorkload(prof, cb, "architecture.arbitration", 1, 4000, true)
		printJSON(map[string]any{
			"workstation": prof,
			"routes":      []compute.RouteDecision{decC0, decC1, decC2},
		})
		return 0

	case "mcp":
		eng, err := harness.NewEngine(rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro ao iniciar MCP: %v\n", err)
			return 1
		}
		srv := mcp.NewServer(rootDir, eng)
		if err := srv.ServeStdio(os.Stdin, os.Stdout); err != nil {
			return 1
		}
		return 0

	case "bench":
		return runLiveBenchmarkSuite(rootDir)

	case "install":
		sub := "all"
		if len(args) > 1 {
			sub = strings.ToLower(strings.TrimSpace(args[1]))
		}
		cat, err := catalog.Load(rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro ao carregar catálogo para install: %v\n", err)
			return 1
		}
		switch sub {
		case "detect", "detectar":
			targets := installer.DetectTargets()
			printJSON(map[string]any{
				"targets_detected": len(targets),
				"targets":          targets,
			})
			return 0
		case "verify", "verificar":
			rep := installer.Verify(cat, nil)
			printJSON(rep)
			if !rep.AllSynced {
				return 1
			}
			return 0
		case "all", "instalar-todos", "sync":
			sum, err := installer.InstallToTargets(cat, nil)
			if err != nil {
				fmt.Fprintf(os.Stderr, "erro ao instalar skills: %v\n", err)
				return 1
			}
			printJSON(sum)
			if len(sum.BlockedSkills) > 0 {
				return 1
			}
			return 0
		default:
			fmt.Fprintf(os.Stderr, "uso: squad-harness install [all|detect|verify]\n")
			return 2
		}

	case "ui":
		addr := "127.0.0.1:9090"
		smoke := false
		for i := 1; i < len(args); i++ {
			switch args[i] {
			case "--smoke":
				smoke = true
			case "--addr", "-a":
				if i+1 < len(args) {
					addr = args[i+1]
					i++
				}
			default:
				if strings.HasPrefix(args[i], "127.0.0.1:") || strings.HasPrefix(args[i], "localhost:") || strings.HasPrefix(args[i], ":") {
					addr = args[i]
				}
			}
		}
		srv, err := ui.NewServer(rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro ao inicializar servidor UI: %v\n", err)
			return 1
		}
		if smoke {
			printJSON(map[string]any{
				"status":       "UI_READY",
				"bind_url":     "http://" + addr,
				"identity":     contracts.FullIdentity,
				"skills_count": srv.SkillsCount(),
				"sekg_nodes":   srv.SEKGNodesCount(),
			})
			return 0
		}
		fmt.Println("======================================================================")
		fmt.Printf(" %s — Catálogo Interativo (%d Skills · %d Nós SEKG)\n", contracts.FullIdentity, srv.SkillsCount(), srv.SEKGNodesCount())
		fmt.Printf(" Acesse no navegador: http://%s\n", addr)
		fmt.Println(" Pressione Ctrl+C para encerrar.")
		fmt.Println("======================================================================")
		httpSrv := &http.Server{
			Addr:              addr,
			Handler:           srv.Handler(),
			ReadHeaderTimeout: 5 * time.Second,
		}
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Fprintf(os.Stderr, "erro no servidor HTTP: %v\n", err)
			return 1
		}
		return 0

	default:
		fmt.Fprintf(os.Stderr, "subcomando desconhecido: %s\n", cmd)
		printUsage()
		return 2
	}
}

func runUnifiedGateDAG(rootDir string) int {
	ctx := context.Background()
	eng := dag.NewEngine(runtime.GOMAXPROCS(0))

	var loadedCat *catalog.Catalog

	_ = eng.AddNode(dag.Node{
		ID:          "stage0.catalog_load",
		Description: "Carregamento único concorrente das 106 skills, agentes e comandos em memória",
		Action: func(ctx context.Context) error {
			cat, err := catalog.Load(rootDir)
			if err != nil {
				return err
			}
			loadedCat = cat
			return nil
		},
	})

	_ = eng.AddNode(dag.Node{
		ID:          "stage1.catalog_validate",
		Description: "Validação de frontmatter, UTF-8, Linha de Defesa de Prompt e drift do registry",
		Deps:        []string{"stage0.catalog_load"},
		Action: func(ctx context.Context) error {
			rep := loadedCat.Validate()
			if rep.UTF8Clean != rep.CanonicalSkills {
				return fmt.Errorf("skills com UTF-8 inválido: %v", rep.Errors)
			}
			return nil
		},
	})

	_ = eng.AddNode(dag.Node{
		ID:          "stage1.jev_tribunal",
		Description: "Fan-out paralelo dos 25 especialistas determinísticos JEV + Tribunal Critic/Judge",
		Deps:        []string{"stage0.catalog_load"},
		Action: func(ctx context.Context) error {
			v := jev.EvaluateTribunal(jev.ReviewInput{})
			if v.GateState != contracts.GatePass {
				return fmt.Errorf("tribunal reprovou: %v", v.Blockers)
			}
			return nil
		},
	})

	_ = eng.AddNode(dag.Node{
		ID:          "stage1.sekg_build",
		Description: "Indexação determinística do Software Engineering Knowledge Graph (CSR + Leiden)",
		Deps:        []string{"stage0.catalog_load"},
		Action: func(ctx context.Context) error {
			g := sekg.IndexRepository(rootDir, loadedCat)
			if len(g.Nodes) == 0 {
				return fmt.Errorf("SEKG vazio")
			}
			return nil
		},
	})

	_ = eng.AddNode(dag.Node{
		ID:          "stage2.delivery_gates",
		Description: "Gates de entrega (environment-infrastructure-gate + database-schema-gate + interop)",
		Deps:        []string{"stage1.catalog_validate", "stage1.jev_tribunal"},
		Action: func(ctx context.Context) error {
			dec := gates.DecidirEntrega(ctx, rootDir, "review", "")
			if !dec.Authorized {
				return fmt.Errorf("gate de entrega: estado=%s subgates=%+v", dec.State, dec.SubGates)
			}
			return nil
		},
	})

	summary, err := eng.Execute(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "erro no DAG: %v\n", err)
		return 1
	}
	printJSON(summary)
	if !summary.Success {
		return 1
	}
	return 0
}

func runLiveBenchmarkSuite(rootDir string) int {
	t0 := time.Now()
	var mBefore, mAfter runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&mBefore)

	// 1. Measure Catalog Load + Validation (106 skills)
	tCat := time.Now()
	cat, err := catalog.Load(rootDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "bench catalog error: %v\n", err)
		return 1
	}
	valRep := cat.Validate()
	catDurMs := float64(time.Since(tCat).Microseconds()) / 1000.0

	// 2. Measure Preflight + Hybrid BM25 + SEKG + GraphRAG (Local, Global, DRIFT)
	tPreflight := time.Now()
	cogEng, err := harness.NewEngine(rootDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "bench harness error: %v\n", err)
		return 1
	}
	pfRes := cogEng.RunPreflight("arquitetura aws step functions lambda go seguranca", []string{"internal/gates/delivery.go"})
	preflightDurMs := float64(time.Since(tPreflight).Microseconds()) / 1000.0

	// 3. Measure GraphRAG Local, Global, and DRIFT Search
	ragEng := graphrag.NewEngine(cogEng.Graph())
	tLocal := time.Now()
	_ = ragEng.LocalSearch(graphrag.QueryRequest{Query: "engenheiro-seguranca", TopK: 5})
	localSearchUs := time.Since(tLocal).Microseconds()

	tGlobal := time.Now()
	_ = ragEng.GlobalSearch(graphrag.QueryRequest{Query: "visao geral comunidades arquitetura", TopK: 5})
	globalSearchUs := time.Since(tGlobal).Microseconds()

	tDrift := time.Now()
	_ = ragEng.DRIFTSearch(graphrag.QueryRequest{Query: "causa raiz impacto gates seguranca", TopK: 5})
	driftSearchUs := time.Since(tDrift).Microseconds()

	// 4. Measure 25 JEV Specialists Tribunal
	tJev := time.Now()
	jevRes := jev.EvaluateTribunal(jev.ReviewInput{
		FilesChanged: []string{"internal/gates/delivery.go"},
		DiffContent:  "func Example() error { return nil }",
	})
	jevDurUs := time.Since(tJev).Microseconds()

	// 5. Measure Hot-Path Hooks
	tHook := time.Now()
	_, _ = hooks.PreToolUse(rootDir, strings.NewReader(`{"tool_name":"Bash","tool_input":{"command":"git status"}}`))
	hookPreUs := time.Since(tHook).Microseconds()

	runtime.ReadMemStats(&mAfter)
	sysMem, _ := jobobject.ProbeSystemMemory()

	report := map[string]any{
		"identity":                   contracts.FullIdentity,
		"go_toolchain":               runtime.Version(),
		"provenance":                 contracts.ProvenanceMeasured,
		"canonical_skills_loaded":    valRep.CanonicalSkills,
		"sekg_nodes":                 len(cogEng.Graph().Nodes),
		"sekg_edges":                 len(cogEng.Graph().Edges),
		"sekg_leiden_communities":    len(cogEng.Graph().Communities),
		"catalog_load_validate_ms":   catDurMs,
		"preflight_full_10stages_ms": preflightDurMs,
		"graphrag_local_search_us":   localSearchUs,
		"graphrag_global_search_us":  globalSearchUs,
		"graphrag_drift_search_us":   driftSearchUs,
		"jev_25_specialists_us":      jevDurUs,
		"jev_verdict":                jevRes.Verdict,
		"hook_pre_tool_us":           hookPreUs,
		"heap_alloc_mb":              float64(mAfter.Alloc) / (1024 * 1024),
		"heap_sys_mb":                float64(mAfter.HeapSys) / (1024 * 1024),
		"host_avail_ram_mb":          sysMem.AvailPhysMB,
		"host_total_ram_mb":          sysMem.TotalPhysMB,
		"top_routed_skill":           pfRes.TopSkills[0].SkillName,
		"total_bench_ms":             float64(time.Since(t0).Microseconds()) / 1000.0,
	}
	printJSON(report)
	return 0
}

func printJSON(v any) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}

func printUsage() {
	fmt.Printf("%s (%s) — Runtime Nativo em Go 1.24.3\n\n", contracts.FullIdentity, contracts.TechnicalName)
	fmt.Println("Subcomandos disponíveis:")
	fmt.Println("  version                       Exibe identidade, versão v0.8.0, toolchain Go e memória livre do host")
	fmt.Println("  gate                          Executa a pipeline de qualidade unificada em DAG (goroutines)")
	fmt.Println("  preflight [query]             Executa os 10 estágios do CognitiveHarness Camada 0 (< 25ms)")
	fmt.Println("  sekg <status|index|query|impact> Opera o Software Engineering Knowledge Graph e GraphRAG")
	fmt.Println("  sync                          Classifica o estado Git via JEV e gera plano de sincronização")
	fmt.Println("  jev [diff]                    Executa os 25 especialistas JEV + Tribunal Critic/Judge")
	fmt.Println("  compute                       Exibe diagnóstico do Cognitive Compute Router (C0/C1/C2)")
	fmt.Println("  hook <pre-tool|post-tool|stop> Executa os hooks de sessão ultra-rápidos (< 15ms)")
	fmt.Println("  mcp                           Inicia o servidor MCP JSON-RPC 2.0 unificado via stdio")
	fmt.Println("  bench                         Executa a suíte de benchmarks reais na estação (RAM + Latência)")
	fmt.Println("  install [all|detect|verify]   Instala/sincroniza as skills em todos os ambientes agênticos (Go nativo)")
	fmt.Println("  ui [--addr 127.0.0.1:9090]    Inicia o Control Center Web nativo embutido no binário")
}
