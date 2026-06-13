package registryeditor

import (
	"errors"
	"runtime"
	"testing"
)

func TestManagerRejectsDuplicateSession(t *testing.T) {
	manager := NewManager()
	if err := manager.Open("session-one"); err != nil {
		t.Fatalf("open session: %v", err)
	}
	if err := manager.Open("session-one"); !errors.Is(err, ErrDuplicateSession) {
		t.Fatalf("expected duplicate session error, got %v", err)
	}
}

func TestNormalizeRegistryFields(t *testing.T) {
	hive, err := NormalizeHive("HKEY_LOCAL_MACHINE")
	if err != nil {
		t.Fatalf("normalize hive: %v", err)
	}
	keyPath, err := NormalizeKeyPath(`\Software//Microsoft\`)
	if err != nil {
		t.Fatalf("normalize key path: %v", err)
	}
	valueType, err := NormalizeValueType("reg_dword")
	if err != nil {
		t.Fatalf("normalize value type: %v", err)
	}
	value, err := NormalizeWritableValue(valueType, "0x2a")
	if err != nil {
		t.Fatalf("normalize writable value: %v", err)
	}

	if hive != "HKLM" {
		t.Fatalf("expected HKLM, got %q", hive)
	}
	if keyPath != `Software\Microsoft` {
		t.Fatalf("unexpected key path %q", keyPath)
	}
	if value != uint32(42) {
		t.Fatalf("expected DWORD 42, got %#v", value)
	}
}

func TestNormalizeRejectsTraversalAndUnsupportedWrites(t *testing.T) {
	if _, err := NormalizeKeyPath(`Software\..\Secret`); !errors.Is(err, ErrInvalidKey) {
		t.Fatalf("expected invalid key, got %v", err)
	}
	if _, err := NormalizeValueType("REG_BINARY"); !errors.Is(err, ErrUnsupportedOperation) {
		t.Fatalf("expected unsupported value type, got %v", err)
	}
}

func TestNonWindowsRegistryOperationsReturnUnsupported(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("non-Windows stub is not active")
	}
	manager := NewManager()
	if err := manager.Open("session-one"); err != nil {
		t.Fatalf("open session: %v", err)
	}

	_, err := manager.ListKey("session-one", "HKCU", "Environment")
	if !errors.Is(err, ErrUnsupportedOperation) {
		t.Fatalf("expected unsupported operation, got %v", err)
	}
}
