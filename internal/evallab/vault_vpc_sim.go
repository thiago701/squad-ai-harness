package evallab

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
)

// ErrVPCZeroTrustViolation indicates a security or routing violation in the simulated VPC topology.
var ErrVPCZeroTrustViolation = errors.New("vault_vpc_sim: zero-trust VPC or Vault policy violation detected")

// SubnetSpec represents a simulated AWS VPC subnet tier.
type SubnetSpec struct {
	Name                string   `json:"name"`
	CIDR                string   `json:"cidr"`
	AZ                  string   `json:"az"`
	Tier                string   `json:"tier"` // Public | PrivateApp | IsolatedVault
	MapPublicIPOnLaunch bool     `json:"map_public_ip_on_launch"`
	Routes              []string `json:"routes"` // e.g., "10.20.0.0/16->local", "pl-s3->vpce-gw-s3"
}

// SecurityGroupRuleSpec represents an inbound/outbound Security Group rule.
type SecurityGroupRuleSpec struct {
	Port            int    `json:"port"`
	Protocol        string `json:"protocol"`
	SourceCIDR      string `json:"source_cidr,omitempty"`
	SourceGroupName string `json:"source_group_name,omitempty"`
}

// SecurityGroupSpec represents a simulated AWS Security Group.
type SecurityGroupSpec struct {
	Name    string                  `json:"name"`
	Ingress []SecurityGroupRuleSpec `json:"ingress"`
}

// VaultLocalStackConfig represents the simulated HashiCorp Vault + LocalStack configuration.
type VaultLocalStackConfig struct {
	SealType              string   `json:"seal_type"` // awskms
	KMSKeyARN             string   `json:"kms_key_arn"`
	KMSEndpoint           string   `json:"kms_endpoint"`
	AWSIAMEndpoint        string   `json:"aws_iam_endpoint"`
	AWSSTSEndpoint        string   `json:"aws_sts_endpoint"`
	IAMServerIDHeader     string   `json:"iam_server_id_header"`
	TLSMinVersion         string   `json:"tls_min_version"`
	DefaultLeaseTTLSec    int      `json:"default_lease_ttl_sec"`
	MaxLeaseTTLSec        int      `json:"max_lease_ttl_sec"`
	PolicyPaths           []string `json:"policy_paths"`
	GatewayEndpoints      []string `json:"gateway_endpoints"`
	PrivateLinkEndpoints  []string `json:"privatelink_endpoints"`
}

// VaultVPCSimulationReport summarizes the deterministic simulation of Vault + AWS VPC + LocalStack.
type VaultVPCSimulationReport struct {
	SimulatedAt          string          `json:"simulated_at"`
	VPCCIDR              string          `json:"vpc_cidr"`
	ZeroTrustVPCValid    bool            `json:"zero_trust_vpc_valid"`
	KMSAutoUnsealValid   bool            `json:"kms_auto_unseal_valid"`
	DynamicSTSCredsValid bool            `json:"dynamic_sts_creds_valid"`
	IAMAuthAntiReplay    bool            `json:"iam_auth_anti_replay"`
	SGChainingValid      bool            `json:"sg_chaining_valid"`
	FinOpsGatewayValid   bool            `json:"finops_gateway_valid"`
	TransitCiphertext    string          `json:"transit_ciphertext"`
	IssuedLeaseID        string          `json:"issued_lease_id"`
	Violations           []string        `json:"violations,omitempty"`
	Verdict              DeliveryVerdict `json:"verdict"`
}

// DefaultCanonicalVaultVPCSpec returns the reference Zero-Trust AWS VPC + Vault + LocalStack specification.
func DefaultCanonicalVaultVPCSpec() ([]SubnetSpec, []SecurityGroupSpec, VaultLocalStackConfig) {
	subnets := []SubnetSpec{
		{
			Name:                "public-az1",
			CIDR:                "10.20.1.0/24",
			AZ:                  "us-east-1a",
			Tier:                "Public",
			MapPublicIPOnLaunch: true,
			Routes:              []string{"10.20.0.0/16->local", "0.0.0.0/0->igw-main"},
		},
		{
			Name:                "private-app-az1",
			CIDR:                "10.20.16.0/24",
			AZ:                  "us-east-1a",
			Tier:                "PrivateApp",
			MapPublicIPOnLaunch: false,
			Routes:              []string{"10.20.0.0/16->local", "pl-s3->vpce-gw-s3", "pl-dynamodb->vpce-gw-ddb", "0.0.0.0/0->nat-az1"},
		},
		{
			Name:                "isolated-vault-az1",
			CIDR:                "10.20.64.0/24",
			AZ:                  "us-east-1a",
			Tier:                "IsolatedVault",
			MapPublicIPOnLaunch: false,
			Routes:              []string{"10.20.0.0/16->local", "pl-s3->vpce-gw-s3", "pl-dynamodb->vpce-gw-ddb"},
		},
	}

	sgs := []SecurityGroupSpec{
		{
			Name: "squad-app-sg",
			Ingress: []SecurityGroupRuleSpec{
				{Port: 8080, Protocol: "tcp", SourceGroupName: "squad-alb-sg"},
			},
		},
		{
			Name: "squad-vault-cluster-sg",
			Ingress: []SecurityGroupRuleSpec{
				{Port: 8200, Protocol: "tcp", SourceGroupName: "squad-app-sg"},
				{Port: 8201, Protocol: "tcp", SourceGroupName: "squad-vault-cluster-sg"},
			},
		},
	}

	cfg := VaultLocalStackConfig{
		SealType:             "awskms",
		KMSKeyARN:            "arn:aws:kms:us-east-1:000000000000:key/vault-unseal-local",
		KMSEndpoint:          "http://localstack:4566",
		AWSIAMEndpoint:       "http://localstack:4566",
		AWSSTSEndpoint:       "http://localstack:4566",
		IAMServerIDHeader:    "vault.internal.squad.local",
		TLSMinVersion:        "tls13",
		DefaultLeaseTTLSec:   900,
		MaxLeaseTTLSec:       3600,
		PolicyPaths:          []string{"secret-squad/data/orders/*", "aws-local/creds/order-s3-writer", "transit/encrypt/pii-key"},
		GatewayEndpoints:     []string{"com.amazonaws.us-east-1.s3", "com.amazonaws.us-east-1.dynamodb"},
		PrivateLinkEndpoints: []string{"com.amazonaws.us-east-1.kms", "com.amazonaws.us-east-1.sts"},
	}

	return subnets, sgs, cfg
}

// SimulateVaultAndVPCInfra validates and simulates the end-to-end Vault + AWS VPC + LocalStack stack.
func SimulateVaultAndVPCInfra(subnets []SubnetSpec, sgs []SecurityGroupSpec, cfg VaultLocalStackConfig) (VaultVPCSimulationReport, error) {
	var violations []string

	vpcValid := validateSubnetsZeroTrust(subnets, &violations)
	sgValid := validateVaultSecurityGroups(sgs, &violations)
	finopsValid := validateEndpointsFinOps(cfg, &violations)
	unsealValid := validateKMSAutoUnseal(cfg, &violations)
	stsValid := validateDynamicSTSAndPolicies(cfg, &violations)
	antiReplay := strings.TrimSpace(cfg.IAMServerIDHeader) != ""
	if !antiReplay {
		violations = append(violations, "missing X-Vault-AWS-IAM-Server-ID anti-replay header")
	}

	transitHash := sha256.Sum256([]byte("pii-payload:" + cfg.KMSKeyARN))
	cipher := "vault:v1:" + hex.EncodeToString(transitHash[:16])
	leaseHash := sha256.Sum256([]byte(cfg.AWSSTSEndpoint + ":" + fmt.Sprint(cfg.DefaultLeaseTTLSec)))
	leaseID := "aws-local/creds/order-s3-writer/" + hex.EncodeToString(leaseHash[:8])

	verdict := VerdictProvenSuccess
	var retErr error
	if len(violations) > 0 {
		verdict = VerdictFailed
		retErr = ErrVPCZeroTrustViolation
	}

	return VaultVPCSimulationReport{
		SimulatedAt:          time.Now().UTC().Format(time.RFC3339),
		VPCCIDR:              "10.20.0.0/16",
		ZeroTrustVPCValid:    vpcValid,
		KMSAutoUnsealValid:   unsealValid,
		DynamicSTSCredsValid: stsValid,
		IAMAuthAntiReplay:    antiReplay,
		SGChainingValid:      sgValid,
		FinOpsGatewayValid:   finopsValid,
		TransitCiphertext:    cipher,
		IssuedLeaseID:        leaseID,
		Violations:           violations,
		Verdict:              verdict,
	}, retErr
}

func validateSubnetsZeroTrust(subnets []SubnetSpec, violations *[]string) bool {
	hasIsolatedVault := false
	ok := true
	for _, sn := range subnets {
		if sn.Tier != "IsolatedVault" {
			continue
		}
		hasIsolatedVault = true
		if sn.MapPublicIPOnLaunch {
			*violations = append(*violations, "IsolatedVault subnet cannot have map_public_ip_on_launch=true")
			ok = false
		}
		if hasDefaultInternetRoute(sn.Routes) {
			*violations = append(*violations, "IsolatedVault subnet cannot have 0.0.0.0/0 route to IGW or NAT")
			ok = false
		}
	}
	if !hasIsolatedVault {
		*violations = append(*violations, "missing IsolatedVault subnet tier")
		return false
	}
	return ok
}

func hasDefaultInternetRoute(routes []string) bool {
	for _, r := range routes {
		if strings.HasPrefix(r, "0.0.0.0/0") {
			return true
		}
	}
	return false
}

func validateVaultSecurityGroups(sgs []SecurityGroupSpec, violations *[]string) bool {
	foundVaultSG := false
	ok := true
	for _, sg := range sgs {
		if sg.Name != "squad-vault-cluster-sg" {
			continue
		}
		foundVaultSG = true
		if !checkVaultRules(sg.Ingress, violations) {
			ok = false
		}
	}
	if !foundVaultSG {
		*violations = append(*violations, "missing squad-vault-cluster-sg security group")
		return false
	}
	return ok
}

func checkVaultRules(rules []SecurityGroupRuleSpec, violations *[]string) bool {
	ok := true
	for _, r := range rules {
		if r.SourceCIDR == "0.0.0.0/0" || strings.HasSuffix(r.SourceCIDR, "/16") {
			*violations = append(*violations, fmt.Sprintf("open CIDR %s on Vault port %d violates SG-to-SG chaining", r.SourceCIDR, r.Port))
			ok = false
		}
		if r.SourceGroupName == "" {
			*violations = append(*violations, "Vault SG ingress rule must reference a source Security Group")
			ok = false
		}
	}
	return ok
}

func validateEndpointsFinOps(cfg VaultLocalStackConfig, violations *[]string) bool {
	hasS3 := false
	for _, ep := range cfg.GatewayEndpoints {
		if strings.HasSuffix(ep, ".s3") {
			hasS3 = true
		}
	}
	if !hasS3 {
		*violations = append(*violations, "missing S3 Gateway VPC Endpoint (FinOps violation)")
	}
	hasKMS := false
	hasSTS := false
	for _, ep := range cfg.PrivateLinkEndpoints {
		if strings.HasSuffix(ep, ".kms") {
			hasKMS = true
		}
		if strings.HasSuffix(ep, ".sts") {
			hasSTS = true
		}
	}
	if !hasKMS || !hasSTS {
		*violations = append(*violations, "missing KMS or STS Interface VPC Endpoint (PrivateLink)")
	}
	return hasS3 && hasKMS && hasSTS
}

func validateKMSAutoUnseal(cfg VaultLocalStackConfig, violations *[]string) bool {
	ok := cfg.SealType == "awskms" &&
		strings.Contains(cfg.KMSEndpoint, "4566") &&
		strings.HasPrefix(cfg.KMSKeyARN, "arn:aws:kms:")
	if !ok {
		*violations = append(*violations, "invalid KMS Auto-Unseal configuration for LocalStack")
	}
	return ok
}

func validateDynamicSTSAndPolicies(cfg VaultLocalStackConfig, violations *[]string) bool {
	ok := strings.Contains(cfg.AWSIAMEndpoint, "4566") &&
		strings.Contains(cfg.AWSSTSEndpoint, "4566") &&
		cfg.DefaultLeaseTTLSec > 0 &&
		cfg.MaxLeaseTTLSec <= 3600
	if !ok {
		*violations = append(*violations, "invalid LocalStack IAM/STS endpoints or lease TTL > 3600s")
	}
	for _, p := range cfg.PolicyPaths {
		if strings.TrimSpace(p) == "*" || strings.TrimSpace(p) == "sys/*" {
			*violations = append(*violations, "wildcard or sys/* root path in workload Vault policy violates least privilege")
			ok = false
		}
	}
	return ok
}
