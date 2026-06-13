package registryeditor

import (
	"errors"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
	"sync"
)

var (
	ErrAccessDenied         = errors.New("access denied")
	ErrDuplicateSession     = errors.New("registry session already exists")
	ErrInvalidHive          = errors.New("registry hive invalid")
	ErrInvalidKey           = errors.New("registry key invalid")
	ErrInvalidValue         = errors.New("registry value invalid")
	ErrNotFound             = errors.New("registry key or value not found")
	ErrUnsupportedOperation = errors.New("unsupported operation")
	ErrUnknownSession       = errors.New("unknown registry session")
)

type Manager struct {
	mu       sync.Mutex
	sessions map[string]struct{}
}

type Listing struct {
	Hive    string   `json:"hive"`
	KeyPath string   `json:"key_path"`
	Subkeys []string `json:"subkeys"`
	Values  []Value  `json:"values"`
}

type Value struct {
	Name     string `json:"name"`
	Type     string `json:"type"`
	Value    any    `json:"value,omitempty"`
	Writable bool   `json:"writable"`
}

func NewManager() *Manager {
	return &Manager{sessions: map[string]struct{}{}}
}

func (m *Manager) Open(id string) error {
	id = strings.TrimSpace(id)
	if id == "" {
		return ErrUnknownSession
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, exists := m.sessions[id]; exists {
		return ErrDuplicateSession
	}
	m.sessions[id] = struct{}{}
	return nil
}

func (m *Manager) Close(id string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, exists := m.sessions[strings.TrimSpace(id)]; !exists {
		return ErrUnknownSession
	}
	delete(m.sessions, strings.TrimSpace(id))
	return nil
}

func (m *Manager) CloseAll() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.sessions = map[string]struct{}{}
}

func (m *Manager) requireSession(id string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, exists := m.sessions[strings.TrimSpace(id)]; !exists {
		return ErrUnknownSession
	}
	return nil
}

func NormalizeHive(value string) (string, error) {
	switch strings.ToUpper(strings.TrimSpace(value)) {
	case "HKCR", "HKEY_CLASSES_ROOT":
		return "HKCR", nil
	case "HKCU", "HKEY_CURRENT_USER":
		return "HKCU", nil
	case "HKLM", "HKEY_LOCAL_MACHINE":
		return "HKLM", nil
	case "HKU", "HKEY_USERS":
		return "HKU", nil
	case "HKCC", "HKEY_CURRENT_CONFIG":
		return "HKCC", nil
	default:
		return "", ErrInvalidHive
	}
}

func NormalizeKeyPath(value string) (string, error) {
	keyPath := strings.Trim(strings.TrimSpace(strings.ReplaceAll(value, "/", `\`)), `\`)
	if strings.ContainsRune(keyPath, 0) {
		return "", ErrInvalidKey
	}
	if keyPath == "" {
		return "", nil
	}
	parts := []string{}
	for _, part := range strings.Split(keyPath, `\`) {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if part == "." || part == ".." {
			return "", ErrInvalidKey
		}
		parts = append(parts, part)
	}
	normalized := strings.Join(parts, `\`)
	if len(normalized) > 512 {
		return "", ErrInvalidKey
	}
	return normalized, nil
}

func NormalizeValueName(value string) (string, error) {
	name := strings.TrimSpace(value)
	if strings.ContainsRune(name, 0) || len(name) > 255 {
		return "", ErrInvalidValue
	}
	return name, nil
}

func NormalizeValueType(value string) (string, error) {
	valueType := strings.ToUpper(strings.TrimSpace(value))
	if valueType != "REG_SZ" && valueType != "REG_DWORD" {
		return "", ErrUnsupportedOperation
	}
	return valueType, nil
}

func NormalizeWritableValue(valueType string, value any) (any, error) {
	switch valueType {
	case "REG_SZ":
		typed, ok := value.(string)
		if !ok || strings.ContainsRune(typed, 0) {
			return nil, ErrInvalidValue
		}
		return typed, nil
	case "REG_DWORD":
		parsed, err := parseDWORD(value)
		if err != nil {
			return nil, err
		}
		return parsed, nil
	default:
		return nil, ErrUnsupportedOperation
	}
}

func SortListing(listing Listing) Listing {
	sort.Strings(listing.Subkeys)
	sort.Slice(listing.Values, func(i int, j int) bool {
		return strings.ToLower(listing.Values[i].Name) < strings.ToLower(listing.Values[j].Name)
	})
	return listing
}

func ErrorCode(err error) string {
	switch {
	case errors.Is(err, ErrAccessDenied):
		return "access_denied"
	case errors.Is(err, ErrInvalidHive):
		return "hive_invalid"
	case errors.Is(err, ErrInvalidKey):
		return "key_invalid"
	case errors.Is(err, ErrInvalidValue):
		return "value_invalid"
	case errors.Is(err, ErrNotFound), errors.Is(err, ErrUnknownSession):
		return "not_found"
	default:
		return "unsupported_operation"
	}
}

func parseDWORD(value any) (uint32, error) {
	var parsed uint64
	switch typed := value.(type) {
	case float64:
		if typed < 0 || typed > math.MaxUint32 || math.Trunc(typed) != typed {
			return 0, ErrInvalidValue
		}
		parsed = uint64(typed)
	case int:
		if typed < 0 {
			return 0, ErrInvalidValue
		}
		parsed = uint64(typed)
	case int64:
		if typed < 0 {
			return 0, ErrInvalidValue
		}
		parsed = uint64(typed)
	case uint32:
		return typed, nil
	case string:
		value := strings.TrimSpace(typed)
		base := 10
		if strings.HasPrefix(strings.ToLower(value), "0x") {
			base = 16
			value = value[2:]
		}
		var err error
		parsed, err = strconv.ParseUint(value, base, 32)
		if err != nil {
			return 0, ErrInvalidValue
		}
	default:
		return 0, ErrInvalidValue
	}
	if parsed > math.MaxUint32 {
		return 0, ErrInvalidValue
	}
	return uint32(parsed), nil
}

func UnsupportedError() error {
	return fmt.Errorf("%w: Windows registry is unavailable on this platform", ErrUnsupportedOperation)
}
