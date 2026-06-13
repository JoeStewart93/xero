//go:build !windows

package registryeditor

func (m *Manager) ListKey(id string, hive string, keyPath string) (Listing, error) {
	if err := m.requireSession(id); err != nil {
		return Listing{}, err
	}
	return Listing{}, UnsupportedError()
}

func (m *Manager) ReadValue(id string, hive string, keyPath string, valueName string) (Value, error) {
	if err := m.requireSession(id); err != nil {
		return Value{}, err
	}
	return Value{}, UnsupportedError()
}

func (m *Manager) WriteValue(id string, hive string, keyPath string, valueName string, valueType string, value any) (Value, error) {
	if err := m.requireSession(id); err != nil {
		return Value{}, err
	}
	return Value{}, UnsupportedError()
}

func (m *Manager) DeleteValue(id string, hive string, keyPath string, valueName string) error {
	if err := m.requireSession(id); err != nil {
		return err
	}
	return UnsupportedError()
}
