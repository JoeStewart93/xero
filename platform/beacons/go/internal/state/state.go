package state

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
)

type RuntimeState struct {
	BeaconID    string `json:"beacon_id"`
	BeaconToken string `json:"beacon_token"`
}

func Load(path string) (RuntimeState, error) {
	content, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return RuntimeState{}, nil
	}
	if err != nil {
		return RuntimeState{}, err
	}
	var state RuntimeState
	if err := json.Unmarshal(content, &state); err != nil {
		return RuntimeState{}, err
	}
	return state, nil
}

func Save(path string, state RuntimeState) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	content, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, content, 0o600)
}
