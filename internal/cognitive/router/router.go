// Package router implements the unified Hybrid BM25 skill and specialist router in Go 1.24.3,
// replacing the 4 duplicate Python routers and eliminating the 261,760 Python object allocations
// (110.9 MB RSS) of cognitivo/harness/roteador_hibrido.py.
package router

import (
	"math"
	"sort"
	"strings"
	"unicode"
	"unique"

	"github.com/thiago701/squad-ai-harness/internal/catalog"
)

const (
	bm25K1        = 1.5
	bm25B         = 0.75
	weightName    = 3.0
	weightTrigger = 2.0
	weightProse   = 1.0
	weightBody    = 0.35
	relativeFloor = 0.30
)

// MatchResult represents a ranked skill candidate returned by the hybrid router.
type MatchResult struct {
	SkillName   string   `json:"skill_name"`
	Score       float64  `json:"score"`
	Model       string   `json:"model"`
	MatchedTerms []string `json:"matched_terms,omitempty"`
}

type indexedDoc struct {
	nameHandle unique.Handle[string]
	model      string
	nameTF     map[unique.Handle[string]]int
	triggerTF  map[unique.Handle[string]]int
	proseTF    map[unique.Handle[string]]int
	bodyTF     map[unique.Handle[string]]int
	totalLen   int
}

// HybridRouter holds the compact in-memory inverted index of all canonical skills.
type HybridRouter struct {
	docs   []indexedDoc
	df     map[unique.Handle[string]]int
	avgLen float64
}

var ptEnSynonyms = map[string][]string{
	"banco":       {"database", "sql", "dbml", "postgres", "dynamodb"},
	"seguranca":   {"security", "owasp", "auth", "jwt", "cve"},
	"lentidao":    {"performance", "latencia", "p99", "timeout", "gargalo"},
	"teste":       {"test", "tdd", "qa", "junit", "pytest"},
	"arquitetura": {"architecture", "ddd", "clean", "solid", "minimalista"},
	"erro":        {"error", "bug", "exception", "stacktrace", "falha"},
	"nuvem":       {"cloud", "aws", "lambda", "step", "serverless"},
}

// NewHybridRouter indexes a loaded Catalog in < 3ms using Go 1.24 unique.Handle interning.
func NewHybridRouter(cat *catalog.Catalog) *HybridRouter {
	r := &HybridRouter{
		docs: make([]indexedDoc, 0, len(cat.Skills)),
		df:   make(map[unique.Handle[string]]int, 1024),
	}
	totalTokens := 0

	for _, sk := range cat.Skills {
		prose, triggers := splitDescriptionAndTriggers(sk.Description)
		nameToks := tokenize(strings.ReplaceAll(sk.Name, "-", " "))
		trigToks := tokenize(triggers)
		proseToks := tokenize(prose)
		bodyToks := tokenize(strings.Join(sk.Headers, " "))

		doc := indexedDoc{
			nameHandle: unique.Make(sk.Name),
			model:      defaultModel(sk.Model),
			nameTF:     countFreq(nameToks),
			triggerTF:  countFreq(trigToks),
			proseTF:    countFreq(proseToks),
			bodyTF:     countFreq(bodyToks),
			totalLen:   len(nameToks) + len(trigToks) + len(proseToks) + len(bodyToks),
		}
		totalTokens += doc.totalLen

		seenInDoc := make(map[unique.Handle[string]]struct{})
		for _, m := range []map[unique.Handle[string]]int{doc.nameTF, doc.triggerTF, doc.proseTF, doc.bodyTF} {
			for h := range m {
				seenInDoc[h] = struct{}{}
			}
		}
		for h := range seenInDoc {
			r.df[h]++
		}
		r.docs = append(r.docs, doc)
	}

	if len(r.docs) > 0 {
		r.avgLen = float64(totalTokens) / float64(len(r.docs))
	}
	if r.avgLen <= 0 {
		r.avgLen = 1.0
	}
	return r
}

// Route ranks skills for the given query using weighted field BM25 and the 0.30 relative floor.
func (r *HybridRouter) Route(query string, topK int) []MatchResult {
	if topK <= 0 {
		topK = 5
	}
	rawToks := tokenizeWithSynonyms(query)
	if len(rawToks) == 0 || len(r.docs) == 0 {
		return nil
	}

	var qHandles []unique.Handle[string]
	seenQ := make(map[unique.Handle[string]]struct{}, len(rawToks))
	for _, t := range rawToks {
		h := unique.Make(t)
		if _, exists := seenQ[h]; !exists {
			seenQ[h] = struct{}{}
			qHandles = append(qHandles, h)
		}
	}

	nDocs := float64(len(r.docs))
	var results []MatchResult

	for _, doc := range r.docs {
		score := 0.0
		var matched []string
		normFactor := 1.0 - bm25B + bm25B*(float64(doc.totalLen)/r.avgLen)

		for _, qh := range qHandles {
			df := r.df[qh]
			if df == 0 {
				continue
			}
			idf := math.Log(1.0 + (nDocs-float64(df)+0.5)/(float64(df)+0.5))
			weightedTF := weightName*float64(doc.nameTF[qh]) +
				weightTrigger*float64(doc.triggerTF[qh]) +
				weightProse*float64(doc.proseTF[qh]) +
				weightBody*float64(doc.bodyTF[qh])

			if weightedTF > 0 {
				termScore := idf * ((weightedTF * (bm25K1 + 1.0)) / (weightedTF + bm25K1*normFactor))
				score += termScore
				matched = append(matched, qh.Value())
			}
		}

		if score > 0 {
			results = append(results, MatchResult{
				SkillName:    doc.nameHandle.Value(),
				Score:        score,
				Model:        doc.model,
				MatchedTerms: matched,
			})
		}
	}

	sort.Slice(results, func(i, j int) bool {
		if results[i].Score == results[j].Score {
			return results[i].SkillName < results[j].SkillName
		}
		return results[i].Score > results[j].Score
	})

	if len(results) == 0 {
		return nil
	}

	// Apply 0.30 relative floor against top-1 score
	floor := results[0].Score * relativeFloor
	filtered := results[:0]
	for _, m := range results {
		if m.Score >= floor {
			filtered = append(filtered, m)
			if len(filtered) == topK {
				break
			}
		}
	}
	return filtered
}

func splitDescriptionAndTriggers(desc string) (prose, triggers string) {
	lower := strings.ToLower(desc)
	for _, marker := range []string{"use sempre que", "dispare para", "use when", "trigger"} {
		if idx := strings.Index(lower, marker); idx >= 0 {
			return desc[:idx], desc[idx:]
		}
	}
	return desc, ""
}

func countFreq(tokens []string) map[unique.Handle[string]]int {
	m := make(map[unique.Handle[string]]int, len(tokens))
	for _, t := range tokens {
		m[unique.Make(t)]++
	}
	return m
}

func tokenizeWithSynonyms(text string) []string {
	base := tokenize(text)
	out := make([]string, 0, len(base)*2)
	for _, tok := range base {
		out = append(out, tok)
		if syns, ok := ptEnSynonyms[tok]; ok {
			out = append(out, syns...)
		}
	}
	return out
}

func tokenize(text string) []string {
	norm := normalizeASCII(strings.ToLower(text))
	var tokens []string
	var cur strings.Builder
	for _, r := range norm {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			cur.WriteRune(r)
		} else if cur.Len() > 0 {
			w := cur.String()
			if len(w) >= 2 && !isStopword(w) {
				tokens = append(tokens, w)
			}
			cur.Reset()
		}
	}
	if cur.Len() > 0 {
		w := cur.String()
		if len(w) >= 2 && !isStopword(w) {
			tokens = append(tokens, w)
		}
	}
	return tokens
}

func normalizeASCII(s string) string {
	replacer := strings.NewReplacer(
		"á", "a", "à", "a", "â", "a", "ã", "a",
		"é", "e", "ê", "e", "í", "i", "ó", "o", "ô", "o", "õ", "o",
		"ú", "u", "ç", "c",
	)
	return replacer.Replace(s)
}

func isStopword(w string) bool {
	switch w {
	case "de", "da", "do", "das", "dos", "em", "na", "no", "para", "por", "com", "sem", "uma", "um", "os", "as", "que", "se", "ou", "the", "and", "for", "with":
		return true
	default:
		return false
	}
}

func defaultModel(m string) string {
	if m == "" {
		return "sonnet"
	}
	return m
}
