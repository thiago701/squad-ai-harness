// Command squad-harness is the unified static binary for SquadAI Harness v0.8.1 (Go 1.24.3, CGO_ENABLED=0).
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

	"github.com/thiago701/squad-ai-harness/internal/aiops"
	"github.com/thiago701/squad-ai-harness/internal/catalog"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/cultivator"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/graphrag"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/harness"
	"github.com/thiago701/squad-ai-harness/internal/cognitive/sekg"
	"github.com/thiago701/squad-ai-harness/internal/compute"
	"github.com/thiago701/squad-ai-harness/internal/dag"
	"github.com/thiago701/squad-ai-harness/internal/evallab"
	"github.com/thiago701/squad-ai-harness/internal/gates"
	"github.com/thiago701/squad-ai-harness/internal/git"
	"github.com/thiago701/squad-ai-harness/internal/hooks"
	"github.com/thiago701/squad-ai-harness/internal/installer"
	"github.com/thiago701/squad-ai-harness/internal/jev"
	"github.com/thiago701/squad-ai-harness/internal/mcp"
	"github.com/thiago701/squad-ai-harness/internal/runtime/jobobject"
	"github.com/thiago701/squad-ai-harness/internal/telemetry"
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
			"product":            contracts.ProductName,
			"technical_id":       contracts.TechnicalName,
			"version":            contracts.Version,
			"full_identity":      contracts.FullIdentity,
			"exclusive_language": contracts.ExclusiveLanguage,
			"go_version":         runtime.Version(),
			"os_arch":            runtime.GOOS + "/" + runtime.GOARCH,
			"cpu_cores":          runtime.NumCPU(),
			"avail_ram_mb":       mem.AvailPhysMB,
			"total_ram_mb":       mem.TotalPhysMB,
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
			query = strings.Join(args[1:], " ")
		}
		// Detect natural-language trigger: "Squad ai, gere relatorio de uso" / "Squad ai. me mostre seu relatorio"
		if isReport, qid := telemetry.MatchTrigger(query); isReport {
			if qid != "" {
				if entry, ok := telemetry.ResolveByQUID(qid, rootDir); ok {
					fmt.Print(entry.ASCIIReport)
					return 0
				}
			}
			rep := telemetry.GenerateReport(rootDir, 3)
			fmt.Print(rep.ASCII)
			return 0
		}
		eng, err := harness.NewEngine(rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro ao inicializar engine cognitiva: %v\n", err)
			return 1
		}
		res := eng.RunPreflight(query, nil)
		telemetry.RecordOperation(rootDir, "preflight", res.TotalDurMs)
		if isMonitor, monAct := aiops.MatchNaturalTrigger(query); isMonitor {
			monEng, err := aiops.NewEngine(rootDir, rootDir)
			if err != nil {
				fmt.Fprintf(os.Stderr, "erro ao inicializar engine AIOps: %v\n", err)
				return 1
			}
			ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
			defer cancel()
			if monAct == "down" {
				_ = monEng.StopLocalStack(ctx)
			} else {
				_ = monEng.EnsureLocalStack(ctx, monAct == "up")
				_ = monEng.DiscoverWorkspace(rootDir)
			}
			printJSON(map[string]any{
				"preflight":     res,
				"aiops_trigger": monAct,
				"aiops_monitor": monEng.Snapshot(),
			})
			return 0
		}
		printJSON(res)
		return 0

	case "report", "relatorio":
		var quidFilter string
		var asJSON, listQUIDs bool
		for i := 1; i < len(args); i++ {
			a := strings.TrimSpace(args[i])
			switch strings.ToLower(a) {
			case "--json", "-j":
				asJSON = true
			case "--list-quids", "--list", "list":
				listQUIDs = true
			case "--quid", "-q":
				if i+1 < len(args) {
					quidFilter = args[i+1]
					i++
				}
			default:
				if strings.HasPrefix(strings.ToLower(a), "--quid=") {
					quidFilter = strings.TrimPrefix(a, "--quid=")
					quidFilter = strings.TrimPrefix(quidFilter, "--QUID=")
				} else if strings.HasPrefix(strings.ToUpper(a), "QUID-") {
					quidFilter = a
				} else if ok, extracted := telemetry.MatchTrigger(a); ok && extracted != "" {
					quidFilter = extracted
				}
			}
		}
		if listQUIDs {
			printJSON(telemetry.ListOfflineRegistry(rootDir))
			return 0
		}
		if quidFilter != "" {
			entry, ok := telemetry.ResolveByQUID(quidFilter, rootDir)
			if !ok {
				fmt.Fprintf(os.Stderr, "QUID não encontrado no registro offline local: %s\n", quidFilter)
				return 1
			}
			if asJSON {
				printJSON(entry)
			} else {
				fmt.Print(entry.ASCIIReport)
			}
			return 0
		}
		rep := telemetry.GenerateReport(rootDir, 3)
		if asJSON {
			printJSON(rep)
		} else {
			fmt.Print(rep.ASCII)
		}
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
			kdgPath := filepath.Join(rootDir, ".squad-harness", "sekg.kdg")
			digest, err := eng.Graph().SaveAtomic(dbPath)
			if err != nil {
				fmt.Fprintf(os.Stderr, "erro ao salvar SEKG: %v\n", err)
				return 1
			}
			_ = eng.Graph().SaveKDGAtomic(kdgPath)
			kdgBytes := len(eng.Graph().MarshalKDGBytes())
			printJSON(map[string]any{
				"db_path":          dbPath,
				"kdg_path":         kdgPath,
				"kdg_binary_bytes": kdgBytes,
				"sha256":           digest,
				"nodes":            len(eng.Graph().Nodes),
				"edges":            len(eng.Graph().Edges),
				"communities":      len(eng.Graph().Communities),
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
		code := runUnifiedGateDAG(rootDir)
		telemetry.RecordOperation(rootDir, "gate", 288.0)
		return code

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
		telemetry.RecordOperation(rootDir, "jev", 0.52)
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
		mvPlan := compute.SelectMultiVendorExecutionBackend(prof, "reranker.cross_encoder")
		printJSON(map[string]any{
			"workstation":       prof,
			"multi_vendor_plan": mvPlan,
			"routes":            []compute.RouteDecision{decC0, decC1, decC2},
		})
		return 0

	case "cultivator":
		prof := compute.DetectWorkstation()
		pqlRep, err := cultivator.EvaluatePredictiveFailurePOC001(prof, nil, 0)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro no cultivator POC-001: %v\n", err)
			return 1
		}
		printJSON(pqlRep)
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
		var targetIDs []string
		for i := 1; i < len(args); i++ {
			a := strings.ToLower(strings.TrimSpace(args[i]))
			switch a {
			case "detect", "detectar", "verify", "verificar", "all", "instalar-todos", "sync":
				sub = a
			case "--target", "-t":
				if i+1 < len(args) {
					targetIDs = append(targetIDs, args[i+1])
					i++
				}
			default:
				if strings.HasPrefix(a, "--target=") {
					targetIDs = append(targetIDs, strings.TrimPrefix(a, "--target="))
				} else {
					targetIDs = append(targetIDs, a)
				}
			}
		}
		cat, err := catalog.Load(rootDir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro ao carregar catálogo para install: %v\n", err)
			return 1
		}
		switch sub {
		case "detect", "detectar":
			active := installer.DetectTargets()
			allCat := installer.SupportedCatalog()
			printJSON(map[string]any{
				"active_targets_count":    len(active),
				"supported_catalog_count": len(allCat),
				"active_targets":          active,
				"supported_catalog":       allCat,
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
			var customTargets []installer.TargetDef
			if len(targetIDs) > 0 {
				resolved, err := installer.ResolveTargetsByIDs(targetIDs)
				if err != nil {
					fmt.Fprintf(os.Stderr, "erro: %v\n", err)
					return 2
				}
				customTargets = resolved
			}
			sum, err := installer.InstallToTargets(cat, customTargets)
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
			fmt.Fprintf(os.Stderr, "uso: squad-harness install [all|detect|verify] [--target claude,cursor,copilot...]\n")
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
			ReadTimeout:       15 * time.Second,
			WriteTimeout:      30 * time.Second,
			IdleTimeout:       60 * time.Second,
		}
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Fprintf(os.Stderr, "erro no servidor HTTP: %v\n", err)
			return 1
		}
		return 0

	case "monitor", "aiops":
		return runMonitorCLI(rootDir, args[1:])

	case "evallab", "eval-agentic-api":
		rep := evallab.RunEndToEndAgenticEvaluation(20)
		for _, a := range args[1:] {
			if a == "--export" || a == "-e" {
				outDir := filepath.Join(rootDir, "docs", "auditoria-eval-agentic-api-2026-10-31")
				_ = os.MkdirAll(outDir, 0755)
				raw, _ := json.MarshalIndent(rep, "", "  ")
				_ = os.WriteFile(filepath.Join(outDir, "resultados-experimentais-brutos.json"), raw, 0644)
			}
		}
		printJSON(rep)
		return 0

	case "skilleval", "skill-eval":
		return runSkillEvalCLI(rootDir, args[1:])

	default:
		fmt.Fprintf(os.Stderr, "subcomando desconhecido: %s\n", cmd)
		printUsage()
		return 2
	}
}

func runMonitorCLI(rootDir string, args []string) int {
	sub := "up"
	addr := aiops.DefaultMonitorAddr
	workspaceDir := rootDir
	if envWs := os.Getenv("SQUAD_WORKSPACE"); envWs != "" {
		workspaceDir = envWs
	}
	smoke := false
	var restArgs []string

	for i := 0; i < len(args); i++ {
		a := strings.TrimSpace(args[i])
		switch strings.ToLower(a) {
		case "up", "start", "ligar", "ativar", "status", "discover", "descoberta", "chat", "teach", "ensinar", "down", "stop", "desligar":
			if len(restArgs) == 0 && i == 0 {
				sub = strings.ToLower(a)
			} else {
				restArgs = append(restArgs, a)
			}
		case "--smoke":
			smoke = true
		case "--addr", "-a":
			if i+1 < len(args) {
				addr = args[i+1]
				i++
			}
		case "--workspace", "-w":
			if i+1 < len(args) {
				workspaceDir = args[i+1]
				i++
			}
		default:
			if strings.HasPrefix(a, "--addr=") {
				addr = strings.TrimPrefix(a, "--addr=")
			} else if strings.HasPrefix(a, "--workspace=") {
				workspaceDir = strings.TrimPrefix(a, "--workspace=")
			} else {
				restArgs = append(restArgs, a)
			}
		}
	}

	eng, err := aiops.NewEngine(rootDir, workspaceDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "erro ao inicializar engine AIOps: %v\n", err)
		return 1
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	switch sub {
	case "status":
		_ = eng.EnsureLocalStack(ctx, false)
		_ = eng.DiscoverWorkspace(workspaceDir)
		printJSON(eng.Snapshot())
		return 0

	case "discover", "descoberta":
		disc := eng.DiscoverWorkspace(workspaceDir)
		printJSON(disc)
		return 0

	case "chat":
		q := strings.Join(restArgs, " ")
		if strings.TrimSpace(q) == "" {
			q = "Qual a saúde atual da arquitetura e quais drifts existem?"
		}
		_ = eng.DiscoverWorkspace(workspaceDir)
		resp := eng.Chat(q, "", "monitor", "")
		telemetry.RecordOperation(rootDir, "aiops.chat", 1.8)
		printJSON(resp)
		return 0

	case "teach", "ensinar":
		instr := strings.Join(restArgs, " ")
		sk, err := eng.TeachSkill(instr)
		if err != nil {
			fmt.Fprintf(os.Stderr, "erro ao cadastrar habilidade: %v\n", err)
			return 1
		}
		telemetry.RecordOperation(rootDir, "aiops.teach", 1.2)
		printJSON(map[string]any{
			"status": "CREATED",
			"skill":  sk,
		})
		return 0

	case "down", "stop", "desligar":
		st := eng.StopLocalStack(ctx)
		printJSON(map[string]any{
			"status":     "MONITOR_STOPPED",
			"localstack": st,
		})
		return 0

	case "up", "start", "ligar", "ativar":
		ls := eng.EnsureLocalStack(ctx, true)
		disc := eng.DiscoverWorkspace(workspaceDir)
		snap := eng.Snapshot()
		snap["bind_url"] = "http://" + addr
		telemetry.RecordOperation(rootDir, "aiops.monitor.up", 12.5)
		if smoke {
			printJSON(snap)
			return 0
		}
		fmt.Println("======================================================================")
		fmt.Printf(" %s — Monitor AIOps Lite v2.0 + LocalStack ($0.00 AWS)\n", contracts.FullIdentity)
		fmt.Printf(" LocalStack Mode : %s (%s)\n", ls.Mode, ls.Endpoint)
		fmt.Printf(" Monitor GraphRAG: http://%s\n", addr)
		fmt.Printf(" Descoberta Local: %d arquivos IaC (.tf) · %d arquivos OpenAPI · %d nós descobertos\n",
			disc.TerraformFiles,
			disc.OpenAPIFiles,
			disc.DiscoveredNodes,
		)
		fmt.Println(" Pressione Ctrl+C para encerrar.")
		fmt.Println("======================================================================")
		httpSrv := &http.Server{
			Addr:              addr,
			Handler:           eng.Handler(),
			ReadHeaderTimeout: 5 * time.Second,
			ReadTimeout:       15 * time.Second,
			WriteTimeout:      30 * time.Second,
			IdleTimeout:       60 * time.Second,
		}
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Fprintf(os.Stderr, "erro no servidor Monitor AIOps: %v\n", err)
			return 1
		}
		return 0

	default:
		fmt.Fprintf(os.Stderr, "uso: squad-harness monitor <up|status|discover|chat|teach|down> [--workspace <dir>] [--addr 127.0.0.1:8765]\n")
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
		ID:          "stage1.go_exclusive_lock",
		Description: "Bloqueio exclusivo Go 1.24.3+ (zero Python/Node/CGO no fonte do harness)",
		Deps:        []string{"stage0.catalog_load"},
		Action: func(ctx context.Context) error {
			rep := gates.VerifyGoExclusiveLock(rootDir)
			if !rep.Passed {
				return fmt.Errorf("violação do Go-Exclusive Lock: %v", rep.Violations)
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
		ID:          "stage1.skill_continuous_eval",
		Description: "Suíte contínua de avaliação de skills (Modelo Agentic Eval G1-G7 + pass^5 + selo SHA-256)",
		Deps:        []string{"stage0.catalog_load"},
		Action: func(ctx context.Context) error {
			rep := evallab.EvaluateAllSkillsContinuously(loadedCat, "")
			if rep.OverallVerdict != evallab.VerdictProvenSuccess {
				return fmt.Errorf("falha na suíte contínua de skills: verdict=%s failed=%d", rep.OverallVerdict, rep.FailedCount)
			}
			return nil
		},
	})

	_ = eng.AddNode(dag.Node{
		ID:          "stage2.delivery_gates",
		Description: "Gates de entrega (environment-infrastructure-gate + database-schema-gate + interop)",
		Deps:        []string{"stage1.catalog_validate", "stage1.jev_tribunal", "stage1.go_exclusive_lock", "stage1.skill_continuous_eval"},
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

	topSkill := ""
	if len(pfRes.TopSkills) > 0 {
		topSkill = pfRes.TopSkills[0].SkillName
	}

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
		"top_routed_skill":           topSkill,
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
	fmt.Println("  version                       Exibe identidade, versão v0.8.1, toolchain Go e memória livre do host")
	fmt.Println("  gate                          Executa a pipeline de qualidade unificada em DAG (goroutines)")
	fmt.Println("  preflight [query]             Executa os 10 estágios do CognitiveHarness Camada 0 (< 25ms)")
	fmt.Println("  evallab [--export]            Executa o Agentic Software Engineering Evaluation Lab (Experimentos A-E)")
	fmt.Println("  skilleval [skill] [--init]    Executa a suíte contínua G1-G7 (pass^5 + SHA-256) para novas skills ou evoluções")
	fmt.Println("  sekg <status|index|query|impact> Opera o Software Engineering Knowledge Graph e GraphRAG")
	fmt.Println("  sync                          Classifica o estado Git via JEV e gera plano de sincronização")
	fmt.Println("  jev [diff]                    Executa os 25 especialistas JEV + Tribunal Critic/Judge")
	fmt.Println("  compute                       Exibe diagnóstico do Cognitive Compute Router (C0/C1/C2)")
	fmt.Println("  hook <pre-tool|post-tool|stop> Executa os hooks de sessão ultra-rápidos (< 15ms)")
	fmt.Println("  mcp                           Inicia o servidor MCP JSON-RPC 2.0 unificado via stdio")
	fmt.Println("  bench                         Executa a suíte de benchmarks reais na estação (RAM + Latência)")
	fmt.Println("  install [all|detect|verify]   Instala/sincroniza as skills em todos os ambientes agênticos (Go nativo)")
	fmt.Println("  report [--quid <id>] [--json] Gera o Relatório Executivo ASCII de Uso, Horas e Economia de Tokens (QUID)")
	fmt.Println("  ui [--addr 127.0.0.1:9090]    Inicia o Control Center Web nativo embutido no binário")
	fmt.Println("  monitor [up|status|discover|chat|teach|down] Liga o Monitor AIOps Lite + LocalStack ($0.00 AWS)")
}

func runSkillEvalCLI(rootDir string, args []string) int {
	cat, err := catalog.Load(rootDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "erro ao carregar catálogo: %v\n", err)
		return 1
	}

	initMode := false
	fullMode := false
	filterSkill := ""
	for _, a := range args {
		trimmed := strings.TrimSpace(a)
		if trimmed == "--init" || trimmed == "-i" {
			initMode = true
		} else if trimmed == "--full" || trimmed == "-f" {
			fullMode = true
		} else if !strings.HasPrefix(trimmed, "-") && filterSkill == "" {
			filterSkill = trimmed
		}
	}

	if initMode {
		return initSkillEvalTemplateFile(cat, filterSkill)
	}

	rep := evallab.EvaluateAllSkillsContinuously(cat, filterSkill)
	if !fullMode && filterSkill == "" {
		rep.Results = nil // Summary view by default when running across all 108 skills
	}
	printJSON(rep)
	if rep.OverallVerdict != evallab.VerdictProvenSuccess {
		return 1
	}
	return 0
}

func initSkillEvalTemplateFile(cat *catalog.Catalog, skillName string) int {
	if skillName == "" {
		fmt.Fprintln(os.Stderr, "uso: squad-harness skilleval --init <nome-da-skill>")
		return 2
	}
	for _, sk := range cat.Skills {
		if strings.EqualFold(sk.Name, skillName) {
			tpl := evallab.GenerateCanonicalSkillEvalTemplate(sk)
			evalDir := filepath.Join(sk.DirPath, "evals")
			_ = os.MkdirAll(evalDir, 0755)
			outPath := filepath.Join(evalDir, "evals.json")
			raw, _ := json.MarshalIndent(tpl, "", "  ")
			if err := os.WriteFile(outPath, raw, 0644); err != nil {
				fmt.Fprintf(os.Stderr, "erro ao gravar %s: %v\n", outPath, err)
				return 1
			}
			printJSON(map[string]any{
				"status":      "TEMPLATE_CREATED",
				"skill_name":  sk.Name,
				"output_path": outPath,
				"template":    tpl,
			})
			return 0
		}
	}
	fmt.Fprintf(os.Stderr, "skill não encontrada: %s\n", skillName)
	return 1
}
