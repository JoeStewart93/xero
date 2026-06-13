//go:build windows

package registryeditor

import (
	"errors"
	"syscall"

	"golang.org/x/sys/windows/registry"
)

func (m *Manager) ListKey(id string, hive string, keyPath string) (Listing, error) {
	if err := m.requireSession(id); err != nil {
		return Listing{}, err
	}
	normalizedHive, normalizedPath, err := normalizeTarget(hive, keyPath)
	if err != nil {
		return Listing{}, err
	}
	key, closeKey, err := openKey(normalizedHive, normalizedPath, registry.ENUMERATE_SUB_KEYS|registry.QUERY_VALUE)
	if err != nil {
		return Listing{}, mapRegistryError(err)
	}
	defer closeKey()

	subkeys, err := key.ReadSubKeyNames(-1)
	if err != nil {
		return Listing{}, mapRegistryError(err)
	}
	names, err := key.ReadValueNames(-1)
	if err != nil {
		return Listing{}, mapRegistryError(err)
	}
	values := make([]Value, 0, len(names))
	for _, name := range names {
		value, err := readRegistryValue(key, name)
		if err != nil {
			continue
		}
		values = append(values, value)
	}
	return SortListing(Listing{Hive: normalizedHive, KeyPath: normalizedPath, Subkeys: subkeys, Values: values}), nil
}

func (m *Manager) ReadValue(id string, hive string, keyPath string, valueName string) (Value, error) {
	if err := m.requireSession(id); err != nil {
		return Value{}, err
	}
	normalizedHive, normalizedPath, err := normalizeTarget(hive, keyPath)
	if err != nil {
		return Value{}, err
	}
	name, err := NormalizeValueName(valueName)
	if err != nil {
		return Value{}, err
	}
	key, closeKey, err := openKey(normalizedHive, normalizedPath, registry.QUERY_VALUE)
	if err != nil {
		return Value{}, mapRegistryError(err)
	}
	defer closeKey()
	value, err := readRegistryValue(key, name)
	if err != nil {
		return Value{}, mapRegistryError(err)
	}
	return value, nil
}

func (m *Manager) WriteValue(id string, hive string, keyPath string, valueName string, valueType string, value any) (Value, error) {
	if err := m.requireSession(id); err != nil {
		return Value{}, err
	}
	normalizedHive, normalizedPath, err := normalizeTarget(hive, keyPath)
	if err != nil {
		return Value{}, err
	}
	name, err := NormalizeValueName(valueName)
	if err != nil {
		return Value{}, err
	}
	normalizedType, err := NormalizeValueType(valueType)
	if err != nil {
		return Value{}, err
	}
	normalizedValue, err := NormalizeWritableValue(normalizedType, value)
	if err != nil {
		return Value{}, err
	}
	key, closeKey, err := openKey(normalizedHive, normalizedPath, registry.SET_VALUE|registry.QUERY_VALUE)
	if err != nil {
		return Value{}, mapRegistryError(err)
	}
	defer closeKey()
	switch normalizedType {
	case "REG_SZ":
		if err := key.SetStringValue(name, normalizedValue.(string)); err != nil {
			return Value{}, mapRegistryError(err)
		}
	case "REG_DWORD":
		if err := key.SetDWordValue(name, normalizedValue.(uint32)); err != nil {
			return Value{}, mapRegistryError(err)
		}
	default:
		return Value{}, ErrUnsupportedOperation
	}
	return readRegistryValue(key, name)
}

func (m *Manager) DeleteValue(id string, hive string, keyPath string, valueName string) error {
	if err := m.requireSession(id); err != nil {
		return err
	}
	normalizedHive, normalizedPath, err := normalizeTarget(hive, keyPath)
	if err != nil {
		return err
	}
	name, err := NormalizeValueName(valueName)
	if err != nil {
		return err
	}
	key, closeKey, err := openKey(normalizedHive, normalizedPath, registry.SET_VALUE)
	if err != nil {
		return mapRegistryError(err)
	}
	defer closeKey()
	return mapRegistryError(key.DeleteValue(name))
}

func normalizeTarget(hive string, keyPath string) (string, string, error) {
	normalizedHive, err := NormalizeHive(hive)
	if err != nil {
		return "", "", err
	}
	normalizedPath, err := NormalizeKeyPath(keyPath)
	if err != nil {
		return "", "", err
	}
	return normalizedHive, normalizedPath, nil
}

func rootKey(hive string) (registry.Key, error) {
	switch hive {
	case "HKCR":
		return registry.CLASSES_ROOT, nil
	case "HKCU":
		return registry.CURRENT_USER, nil
	case "HKLM":
		return registry.LOCAL_MACHINE, nil
	case "HKU":
		return registry.USERS, nil
	case "HKCC":
		return registry.CURRENT_CONFIG, nil
	default:
		return 0, ErrInvalidHive
	}
}

func openKey(hive string, keyPath string, access uint32) (registry.Key, func(), error) {
	root, err := rootKey(hive)
	if err != nil {
		return 0, func() {}, err
	}
	if keyPath == "" {
		return root, func() {}, nil
	}
	key, err := registry.OpenKey(root, keyPath, access)
	if err != nil {
		return 0, func() {}, err
	}
	return key, func() { _ = key.Close() }, nil
}

func readRegistryValue(key registry.Key, name string) (Value, error) {
	_, valueType, err := key.GetValue(name, nil)
	if err != nil {
		return Value{}, err
	}
	result := Value{Name: name, Type: valueTypeName(valueType), Writable: valueType == registry.SZ || valueType == registry.DWORD}
	switch valueType {
	case registry.SZ, registry.EXPAND_SZ:
		value, _, err := key.GetStringValue(name)
		if err != nil {
			return Value{}, err
		}
		result.Value = value
	case registry.DWORD:
		value, _, err := key.GetIntegerValue(name)
		if err != nil {
			return Value{}, err
		}
		result.Value = uint32(value)
	case registry.QWORD:
		value, _, err := key.GetIntegerValue(name)
		if err == nil {
			result.Value = value
		}
	case registry.MULTI_SZ:
		value, _, err := key.GetStringsValue(name)
		if err == nil {
			result.Value = value
		}
	}
	return result, nil
}

func valueTypeName(valueType uint32) string {
	switch valueType {
	case registry.SZ:
		return "REG_SZ"
	case registry.EXPAND_SZ:
		return "REG_EXPAND_SZ"
	case registry.BINARY:
		return "REG_BINARY"
	case registry.DWORD:
		return "REG_DWORD"
	case registry.DWORD_BIG_ENDIAN:
		return "REG_DWORD_BIG_ENDIAN"
	case registry.LINK:
		return "REG_LINK"
	case registry.MULTI_SZ:
		return "REG_MULTI_SZ"
	case registry.QWORD:
		return "REG_QWORD"
	default:
		return "REG_NONE"
	}
}

func mapRegistryError(err error) error {
	if err == nil {
		return nil
	}
	if errors.Is(err, registry.ErrNotExist) {
		return ErrNotFound
	}
	if errors.Is(err, syscall.ERROR_ACCESS_DENIED) {
		return ErrAccessDenied
	}
	return err
}
