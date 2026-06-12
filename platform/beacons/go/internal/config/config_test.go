package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadAppliesCompileFileAndEnvPrecedence(t *testing.T) {
	t.Setenv("XERO_BEACON_C2_URL", "http://env-c2:8001")
	t.Setenv("XERO_BEACON_SLEEP_SECONDS", "45")
	configPath := filepath.Join(t.TempDir(), "beacon.json")
	if err := os.WriteFile(
		configPath,
		[]byte(`{"c2_url":"http://file-c2:8001","c2_public_key_b64":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","sleep_seconds":10,"jitter":0.2}`),
		0o600,
	); err != nil {
		t.Fatal(err)
	}

	cfg, err := Load([]string{"-config", configPath})
	if err != nil {
		t.Fatal(err)
	}

	if cfg.C2URL != "http://env-c2:8001" {
		t.Fatalf("expected env c2 url, got %q", cfg.C2URL)
	}
	if cfg.SleepSeconds != 45 {
		t.Fatalf("expected env sleep override, got %d", cfg.SleepSeconds)
	}
	if cfg.Jitter != 0.2 {
		t.Fatalf("expected file jitter, got %f", cfg.Jitter)
	}
	if cfg.StatePath == "" || cfg.MachineFingerprintHash == "" {
		t.Fatalf("expected runtime defaults, got state=%q fingerprint=%q", cfg.StatePath, cfg.MachineFingerprintHash)
	}
}

func TestLoadRejectsInvalidTransport(t *testing.T) {
	t.Setenv("XERO_BEACON_C2_URL", "http://c2.local:8001")
	t.Setenv("XERO_BEACON_C2_PUBLIC_KEY_B64", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
	t.Setenv("XERO_BEACON_TRANSPORT", "carrier-wave")

	_, err := Load(nil)
	if err == nil {
		t.Fatal("expected invalid transport error")
	}
}
