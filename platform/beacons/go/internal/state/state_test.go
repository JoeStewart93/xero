package state

import (
	"path/filepath"
	"testing"
)

func TestStateSaveAndLoad(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state", "beacon.json")
	expected := RuntimeState{BeaconID: "beacon-one", BeaconToken: "token-one"}

	if err := Save(path, expected); err != nil {
		t.Fatal(err)
	}
	actual, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if actual != expected {
		t.Fatalf("expected %#v, got %#v", expected, actual)
	}
}

func TestMissingStateReturnsEmpty(t *testing.T) {
	actual, err := Load(filepath.Join(t.TempDir(), "missing.json"))
	if err != nil {
		t.Fatal(err)
	}
	if actual.BeaconID != "" || actual.BeaconToken != "" {
		t.Fatalf("expected empty state, got %#v", actual)
	}
}
