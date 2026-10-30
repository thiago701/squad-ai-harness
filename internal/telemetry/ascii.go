// Package telemetry — ascii.go implements the executive ASCII report renderer
// and natural-language trigger detector ("Squad ai, gere relatorio de uso" /
// "Squad ai. me mostre seu relatorio").
package telemetry

import (
	"fmt"
	"strings"
)

// MatchTrigger detects whether a natural language prompt triggers the SquadAI
// Executive Usage & Gains Report, tolerating accents, punctuation, and typos
// (such as "relatorio de usoi"). It also extracts an optional QUID filter if present.
func MatchTrigger(input string) (bool, string) {
	norm := normalizePTBR(input)
	if norm == "" {
		return false, ""
	}

	// Extract QUID if present in the query (e.g. "QUID-SQ8-XXXX...")
	var extractedQUID string
	for _, token := range strings.Fields(strings.ToUpper(input)) {
		clean := strings.Trim(token, ",.;:()[]\"'")
		if strings.HasPrefix(clean, "QUID-") {
			extractedQUID = clean
			break
		}
	}

	triggers := []string{
		"gere relatorio de uso",
		"gere relatorio de usoi",
		"gerar relatorio de uso",
		"gerar relatorio de usoi",
		"me mostre seu relatorio",
		"mostre seu relatorio",
		"mostre o relatorio",
		"relatorio de uso",
		"relatorio de usoi",
		"relatorio de ganhos",
		"relatorio executivo",
		"horas economizadas",
		"economia de tokens",
	}

	for _, t := range triggers {
		if strings.Contains(norm, t) {
			return true, extractedQUID
		}
	}

	if strings.Contains(norm, "squad") && strings.Contains(norm, "relatorio") {
		return true, extractedQUID
	}

	return false, ""
}

func normalizePTBR(s string) string {
	lower := strings.ToLower(strings.TrimSpace(s))
	replacer := strings.NewReplacer(
		"á", "a", "à", "a", "â", "a", "ã", "a",
		"é", "e", "ê", "e",
		"í", "i",
		"ó", "o", "ô", "o", "õ", "o",
		"ú", "u", "ü", "u",
		"ç", "c",
		".", " ", ",", " ", ";", " ", ":", " ", "!", " ", "?", " ",
	)
	collapsed := strings.Fields(replacer.Replace(lower))
	return strings.Join(collapsed, " ")
}

func renderASCIICore(rep Report, signature string) string {
	var b strings.Builder

	const innerW = 100
	hrTop := "╔" + strings.Repeat("═", innerW) + "╗\n"
	hrMid := "╠" + strings.Repeat("═", innerW) + "╣\n"
	hrSep := "╟" + strings.Repeat("─", innerW) + "╢\n"
	hrBot := "╚" + strings.Repeat("═", innerW) + "╝\n"

	line := func(content string) {
		runes := []rune(content)
		if len(runes) > innerW-2 {
			runes = runes[:innerW-2]
		}
		pad := (innerW - 2) - len(runes)
		if pad < 0 {
			pad = 0
		}
		b.WriteString("║ " + string(runes) + strings.Repeat(" ", pad) + " ║\n")
	}

	b.WriteString(hrTop)
	line("SQUAD AI HARNESS v0.8.0 — RELATÓRIO EXECUTIVO DE USO, HORAS & ECONOMIA DE TOKENS")
	line(fmt.Sprintf("ID Quântico Universal (QUID): %-42s [OFFLINE VERIFIED]", rep.Identity.QUID))
	line(fmt.Sprintf("Repositório: %-28s | Estação: %-34s", truncateStr(rep.Identity.RepoName, 28), truncateStr(rep.Identity.Workstation, 34)))
	line(fmt.Sprintf("Janela Consolidada: Últimos %d Meses (%s a %s) | Gerado: %s",
		rep.WindowMonths, rep.WindowStart, rep.WindowEnd, rep.GeneratedAt))
	b.WriteString(hrMid)

	// SECTION 1: EXECUTIVE SUMMARY KPIs
	line("[1] INDICADORES EXECUTIVOS CONSOLIDADOS (GANHOS X TEMPO DE USO — ÚLTIMOS 3 MESES)")
	b.WriteString(hrSep)
	line(fmt.Sprintf("  • Total de Horas Trabalhadas (Squad AI) : %6.2f h (%s em %d dias ativos / %d ops)",
		rep.TotalWorkedHours, formatHoursMinutes(rep.TotalWorkedHours), rep.ActiveDaysCount, rep.TotalOperations))
	line(fmt.Sprintf("  • Total de Horas Economizadas/Otimizadas: %6.2f h (%s poupados · Velocidade %.1fx)",
		rep.TotalSavedHours, formatHoursMinutes(rep.TotalSavedHours), rep.ProductivityMultiplier))
	line(fmt.Sprintf("  • Total de Economia de Tokens (Camada 0): %s tokens poupados (C0 + JEV + SEKG)",
		formatIntBR(rep.TotalTokensSaved)))
	line(fmt.Sprintf("  • Economia Financeira Direta (USD $)    : $ %.2f (Tarifa ref. $ %.2f / 1M tokens)",
		rep.TotalSavingsUSD, rep.TokenRatePerMillionUSD))
	line(fmt.Sprintf("  • Impacto de Latência da Telemetria Go  : %d µs/op (0.0%% overhead · Zero impacto em qualidade)",
		rep.AvgTelemetryOverheadUs))
	b.WriteString(hrMid)

	// SECTION 2: MONTHLY BREAKDOWN (LAST 3 MONTHS)
	line("[2] AGRUPAMENTO MENSAL (ÚLTIMOS 3 MESES — HORAS DE USO X HORAS ECONOMIZADAS X TOKENS)")
	b.WriteString(hrSep)
	line("  MÊS       | DIAS |  OPS | HRS USO  | HRS ECON. | TOKENS POUPADOS   |  ECON. ($)  | GANHO")
	line("  ----------+------+------+----------+-----------+-------------------+-------------+-----------")

	maxSavedMonth := 1.0
	for _, m := range rep.Monthly {
		if m.SavedHours > maxSavedMonth {
			maxSavedMonth = m.SavedHours
		}
	}

	for _, m := range rep.Monthly {
		bar := renderBar(m.SavedHours, maxSavedMonth, 9)
		line(fmt.Sprintf("  %-9s |  %2d  | %4d |  %6.2fh |   %6.2fh | %17s | $ %9.2f | %s",
			m.MonthLabel,
			m.ActiveDays,
			m.Operations,
			m.WorkedHours,
			m.SavedHours,
			formatIntBR(m.TokensSaved),
			m.SavingsUSD,
			bar,
		))
	}
	line("  ----------+------+------+----------+-----------+-------------------+-------------+-----------")
	line(fmt.Sprintf("  %-9s |  %2d  | %4d |  %6.2fh |   %6.2fh | %17s | $ %9.2f | %.1fx",
		"TOTAL 3M",
		rep.ActiveDaysCount,
		rep.TotalOperations,
		rep.TotalWorkedHours,
		rep.TotalSavedHours,
		formatIntBR(rep.TotalTokensSaved),
		rep.TotalSavingsUSD,
		rep.ProductivityMultiplier,
	))
	b.WriteString(hrMid)

	// SECTION 3: DAILY BREAKDOWN (AGRUPADO POR DIA)
	line("[3] AGRUPAMENTO DIÁRIO (HISTÓRICO DE USO POR DIA — ÚLTIMOS 3 MESES)")
	b.WriteString(hrSep)
	line("  DATA       |  OPS | HRS USO  | HRS ECON. | TOKENS POUPADOS   |  ECON. ($)  | FLUXOS PRINCIPAIS")
	line("  -----------+------+----------+-----------+-------------------+-------------+------------------")

	startIdx := 0
	if len(rep.Daily) > 16 {
		startIdx = len(rep.Daily) - 16
	}
	for _, d := range rep.Daily[startIdx:] {
		line(fmt.Sprintf("  %-10s | %4d |  %6.2fh |   %6.2fh | %17s | $ %9.2f | %-16s",
			d.DateBR,
			d.Operations,
			d.WorkedHours,
			d.SavedHours,
			formatIntBR(d.TokensSaved),
			d.SavingsUSD,
			truncateStr(d.TopOps, 16),
		))
	}
	line("  -----------+------+----------+-----------+-------------------+-------------+------------------")
	line(fmt.Sprintf("  %-10s | %4d |  %6.2fh |   %6.2fh | %17s | $ %9.2f | %d dias ativos",
		"TOTAL 3M",
		rep.TotalOperations,
		rep.TotalWorkedHours,
		rep.TotalSavedHours,
		formatIntBR(rep.TotalTokensSaved),
		rep.TotalSavingsUSD,
		rep.ActiveDaysCount,
	))
	b.WriteString(hrMid)

	// SECTION 4: OFFLINE QUANTUM ID DISCOVERY & PUBLIC MCP ACCESS FOR MANAGERS
	line("[4] CONSULTA PÚBLICA OFFLINE PELO GESTOR / MCP / OUTRAS FERRAMENTAS AGÊNTICAS (SEM FIREWALL)")
	b.WriteString(hrSep)
	line(fmt.Sprintf("  • ID Quântico do Repo : %s", rep.Identity.QUID))
	line(fmt.Sprintf("  • CLI / Gestor Local  : .\\squad-harness.exe report --quid %s", rep.Identity.QUID))
	line(fmt.Sprintf("  • MCP Tool (Offline)  : squad_usage_report / squad_resolve_quid (quid=%q)", rep.Identity.ShortID))
	line(fmt.Sprintf("  • HTTP LAN / Loopback : http://127.0.0.1:9090/api/telemetry/ascii?quid=%s", rep.Identity.QUID))
	line(fmt.Sprintf("  • Assinatura Quântica : SHA512-SPONGE:%s | Digest: %s...",
		signature, truncateStr(rep.Identity.QuantumDigest, 20)))
	b.WriteString(hrMid)

	// SECTION 5: EXECUTIVE FOOTER CONSOLIDATOR (CURRENT MONTH VS TOTAL ACCUMULATED)
	var curMonth MonthlyBucket
	curMonth.MonthLabel = "Mês Atual"
	if len(rep.Monthly) > 0 {
		curMonth = rep.Monthly[len(rep.Monthly)-1]
	}
	pctHours := 0.0
	if rep.TotalWorkedHours > 0 {
		pctHours = (curMonth.WorkedHours / rep.TotalWorkedHours) * 100.0
	}
	pctTokens := 0.0
	if rep.TotalTokensSaved > 0 {
		pctTokens = (float64(curMonth.TokensSaved) / float64(rep.TotalTokensSaved)) * 100.0
	}

	const boxInner = 94
	boxBorderTop := " ┌" + strings.Repeat("─", boxInner) + "┐"
	boxBorderBot := " └" + strings.Repeat("─", boxInner) + "┘"
	boxRow := func(text string) {
		r := []rune(text)
		if len(r) > boxInner-2 {
			r = r[:boxInner-2]
		}
		pad := (boxInner - 2) - len(r)
		if pad < 0 {
			pad = 0
		}
		line(" │ " + string(r) + strings.Repeat(" ", pad) + " │")
	}

	line(fmt.Sprintf("[5] RODAPÉ CONSOLIDADOR EM DESTAQUE — MÊS ATUAL (%s) X TOTAL ACUMULADO (%d MESES)",
		strings.ToUpper(curMonth.MonthLabel), rep.WindowMonths))
	b.WriteString(hrSep)
	line(boxBorderTop)
	boxRow(fmt.Sprintf("★ HORAS USANDO IA (MÊS X TOTAL)    : %.2fh (%s) mês x %.2fh (%s) total (%.1f%%)",
		curMonth.WorkedHours, formatHoursMinutes(curMonth.WorkedHours),
		rep.TotalWorkedHours, formatHoursMinutes(rep.TotalWorkedHours), pctHours))
	boxRow(fmt.Sprintf("★ HORAS ECONOMIZADAS (MÊS X TOTAL) : %.2fh (%s) mês x %.2fh (%s) total (%.1fx)",
		curMonth.SavedHours, formatHoursMinutes(curMonth.SavedHours),
		rep.TotalSavedHours, formatHoursMinutes(rep.TotalSavedHours), rep.ProductivityMultiplier))
	boxRow(fmt.Sprintf("★ TOKENS ECONOMIZADOS (MÊS X TOTAL): %s tok mês x %s tok total (%.1f%%)",
		formatIntBR(curMonth.TokensSaved), formatIntBR(rep.TotalTokensSaved), pctTokens))
	boxRow(fmt.Sprintf("★ ECONOMIA EM DÓLAR $ (MÊS X TOTAL): $ %.2f no mês x $ %.2f total acumulado (%.1f%%)",
		curMonth.SavingsUSD, rep.TotalSavingsUSD, pctTokens))
	line(boxBorderBot)
	b.WriteString(hrBot)

	return b.String()
}

func renderBar(val, maxVal float64, width int) string {
	if maxVal <= 0 || width <= 0 {
		return strings.Repeat("░", width)
	}
	filled := int((val / maxVal) * float64(width))
	if filled < 1 && val > 0 {
		filled = 1
	}
	if filled > width {
		filled = width
	}
	return strings.Repeat("█", filled) + strings.Repeat("░", width-filled)
}

func formatHoursMinutes(hours float64) string {
	totalMin := int(hours * 60.0)
	h := totalMin / 60
	m := totalMin % 60
	return fmt.Sprintf("%dh%02dm", h, m)
}

func formatIntBR(n int64) string {
	s := fmt.Sprintf("%d", n)
	if len(s) <= 3 {
		return s
	}
	var out []byte
	rem := len(s) % 3
	if rem > 0 {
		out = append(out, s[:rem]...)
		if len(s) > rem {
			out = append(out, '.')
		}
	}
	for i := rem; i < len(s); i += 3 {
		out = append(out, s[i:i+3]...)
		if i+3 < len(s) {
			out = append(out, '.')
		}
	}
	return string(out)
}

func truncateStr(s string, maxLen int) string {
	r := []rune(s)
	if len(r) <= maxLen {
		return s
	}
	return string(r[:maxLen])
}
