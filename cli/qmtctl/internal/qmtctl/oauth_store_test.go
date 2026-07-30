package qmtctl

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/oauth2"
)

func TestOAuthSessionStoreRoundTripPermissionsAndDelete(t *testing.T) {
	path := filepath.Join(t.TempDir(), "nested", "oauth.json")
	store, err := newOAuthSessionStore(path)
	if err != nil {
		t.Fatal(err)
	}
	config := &oauth2.Config{
		ClientID: "public-client",
		Endpoint: oauth2.Endpoint{
			AuthURL:   "https://auth.example.com/authorize",
			TokenURL:  "https://auth.example.com/token",
			AuthStyle: oauth2.AuthStyleInParams,
		},
		Scopes: []string{"qmt:read", "qmt:market"},
	}
	token := &oauth2.Token{
		AccessToken:  "access-secret",
		TokenType:    "Bearer",
		RefreshToken: "refresh-secret",
		Expiry:       time.Now().Add(time.Hour).UTC().Truncate(time.Second),
	}
	if err := store.Save("HTTPS://QMT.EXAMPLE.COM/mcp/", config, token, "preregistered"); err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS != "windows" {
		info, err := os.Stat(path)
		if err != nil {
			t.Fatal(err)
		}
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("store mode = %o", info.Mode().Perm())
		}
		if dirInfo, err := os.Stat(filepath.Dir(path)); err != nil || dirInfo.Mode().Perm() != 0o700 {
			t.Fatalf("directory permissions err=%v mode=%v", err, dirInfo.Mode().Perm())
		}
	}
	loadedConfig, loadedToken, session, err := store.Load("https://qmt.example.com/mcp")
	if err != nil {
		t.Fatal(err)
	}
	if loadedConfig.ClientID != config.ClientID || loadedConfig.Endpoint != config.Endpoint {
		t.Fatalf("loaded config = %#v", loadedConfig)
	}
	if loadedToken.AccessToken != token.AccessToken || loadedToken.RefreshToken != token.RefreshToken {
		t.Fatal("token did not round-trip")
	}
	if session.Registration != "preregistered" {
		t.Fatalf("registration = %q", session.Registration)
	}
	deleted, err := store.Delete("https://qmt.example.com/mcp")
	if err != nil || !deleted {
		t.Fatalf("delete = %v err=%v", deleted, err)
	}
	if _, _, _, err := store.Load("https://qmt.example.com/mcp"); err != ErrOAuthSessionNotFound {
		t.Fatalf("load after delete err = %v", err)
	}
}

func TestOAuthSessionStoreRefusesClientSecrets(t *testing.T) {
	store, err := newOAuthSessionStore(filepath.Join(t.TempDir(), "oauth.json"))
	if err != nil {
		t.Fatal(err)
	}
	config := &oauth2.Config{ClientID: "confidential", ClientSecret: "must-not-persist"}
	err = store.Save(
		"https://qmt.example.com/mcp",
		config,
		&oauth2.Token{AccessToken: "access"},
		"preregistered",
	)
	if err == nil || !strings.Contains(err.Error(), "client secrets") {
		t.Fatalf("save error = %v", err)
	}
}

func TestOAuthSessionStoreKeepsQueryResourcesDistinctAndRejectsFragments(t *testing.T) {
	store, err := newOAuthSessionStore(filepath.Join(t.TempDir(), "oauth.json"))
	if err != nil {
		t.Fatal(err)
	}
	config := &oauth2.Config{ClientID: "public-client"}
	for _, resource := range []string{
		"https://qmt.example.com/mcp?tenant=a",
		"https://qmt.example.com/mcp?tenant=b",
	} {
		if err := store.Save(resource, config, &oauth2.Token{AccessToken: resource}, "preregistered"); err != nil {
			t.Fatal(err)
		}
	}
	_, tokenA, _, err := store.Load("https://qmt.example.com/mcp?tenant=a")
	if err != nil {
		t.Fatal(err)
	}
	if tokenA.AccessToken != "https://qmt.example.com/mcp?tenant=a" {
		t.Fatal("query-distinct resource session was overwritten")
	}
	if err := store.Save(
		"https://qmt.example.com/mcp#fragment",
		config,
		&oauth2.Token{AccessToken: "access"},
		"preregistered",
	); err == nil {
		t.Fatal("fragment resource was accepted")
	}
}

func TestOAuthSessionStoreSerializesConcurrentWriters(t *testing.T) {
	path := filepath.Join(t.TempDir(), "oauth.json")
	first, _ := newOAuthSessionStore(path)
	second, _ := newOAuthSessionStore(path)
	start := make(chan struct{})
	var wait sync.WaitGroup
	errs := make(chan error, 2)
	for index, store := range []*oauthSessionStore{first, second} {
		wait.Add(1)
		go func(index int, store *oauthSessionStore) {
			defer wait.Done()
			<-start
			resource := fmt.Sprintf("https://qmt.example.com/mcp/%d", index)
			errs <- store.Save(
				resource,
				&oauth2.Config{ClientID: fmt.Sprintf("client-%d", index)},
				&oauth2.Token{AccessToken: fmt.Sprintf("access-%d", index)},
				"preregistered",
			)
		}(index, store)
	}
	close(start)
	wait.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatal(err)
		}
	}
	for index, store := range []*oauthSessionStore{first, second} {
		_, token, _, err := store.Load(fmt.Sprintf("https://qmt.example.com/mcp/%d", index))
		if err != nil {
			t.Fatal(err)
		}
		if token.AccessToken != fmt.Sprintf("access-%d", index) {
			t.Fatalf("session %d was lost", index)
		}
	}
}

func TestAuthLogoutRemovesOnlyTheSelectedResource(t *testing.T) {
	t.Setenv("QMT_MCP_ACCESS_TOKEN", "")
	t.Setenv("QMT_MCP_TOKEN", "")
	path := filepath.Join(t.TempDir(), "oauth.json")
	store, _ := newOAuthSessionStore(path)
	config := &oauth2.Config{ClientID: "public-client"}
	for _, resource := range []string{"https://one.example.com/mcp", "https://two.example.com/mcp"} {
		if err := store.Save(
			resource,
			config,
			&oauth2.Token{AccessToken: resource},
			"preregistered",
		); err != nil {
			t.Fatal(err)
		}
	}
	var stdout, stderr bytes.Buffer
	code := Run(
		[]string{
			"--url", "https://one.example.com/mcp",
			"--auth-store", path,
			"--json",
			"auth", "logout",
		},
		&stdout,
		&stderr,
	)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if _, _, _, err := store.Load("https://one.example.com/mcp"); !errors.Is(err, ErrOAuthSessionNotFound) {
		t.Fatalf("selected session still exists: %v", err)
	}
	if _, _, _, err := store.Load("https://two.example.com/mcp"); err != nil {
		t.Fatalf("unrelated session was removed: %v", err)
	}
}

func TestAuthStatusNeverPrintsTokenMaterial(t *testing.T) {
	t.Setenv("QMT_MCP_ACCESS_TOKEN", "")
	t.Setenv("QMT_MCP_TOKEN", "")
	path := filepath.Join(t.TempDir(), "oauth.json")
	store, err := newOAuthSessionStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Save(
		"https://qmt.example.com/mcp",
		&oauth2.Config{
			ClientID: "public-client",
			Endpoint: oauth2.Endpoint{AuthURL: "https://auth.example.com/auth", TokenURL: "https://auth.example.com/token"},
			Scopes:   []string{"qmt:read"},
		},
		&oauth2.Token{AccessToken: "access-secret", RefreshToken: "refresh-secret", Expiry: time.Now().Add(time.Hour)},
		"client_id_metadata",
	); err != nil {
		t.Fatal(err)
	}

	var stdout, stderr bytes.Buffer
	code := Run(
		[]string{
			"--url", "https://qmt.example.com/mcp",
			"--auth-store", path,
			"--json",
			"auth", "status",
		},
		&stdout,
		&stderr,
	)
	if code != 0 {
		t.Fatalf("exit %d stderr=%s", code, stderr.String())
	}
	if strings.Contains(stdout.String(), "access-secret") || strings.Contains(stdout.String(), "refresh-secret") {
		t.Fatalf("status leaked token material: %s", stdout.String())
	}
	var status map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &status); err != nil {
		t.Fatal(err)
	}
	if status["logged_in"] != true || status["client_id"] != "public-client" {
		t.Fatalf("status = %#v", status)
	}
}

func TestSavedOAuthSessionRefreshesAndPersistsForHealth(t *testing.T) {
	t.Setenv("QMT_MCP_ACCESS_TOKEN", "")
	t.Setenv("QMT_MCP_TOKEN", "")
	var tokenRequests int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/token":
			tokenRequests++
			if err := r.ParseForm(); err != nil {
				t.Errorf("parse refresh form: %v", err)
			}
			if r.Form.Get("grant_type") != "refresh_token" || r.Form.Get("refresh_token") != "old-refresh" {
				t.Errorf("refresh form = %#v", r.Form)
			}
			w.Header().Set("content-type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"access_token":  "new-access",
				"refresh_token": "new-refresh",
				"token_type":    "Bearer",
				"expires_in":    3600,
			})
		case "/healthz":
			if r.Header.Get("authorization") != "Bearer new-access" {
				t.Errorf("authorization = %q", r.Header.Get("authorization"))
				http.Error(w, "unauthorized", http.StatusUnauthorized)
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "server": "live"})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	path := filepath.Join(t.TempDir(), "oauth.json")
	store, err := newOAuthSessionStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Save(
		server.URL+"/mcp",
		&oauth2.Config{
			ClientID: "public-client",
			Endpoint: oauth2.Endpoint{
				AuthURL:   server.URL + "/authorize",
				TokenURL:  server.URL + "/token",
				AuthStyle: oauth2.AuthStyleInParams,
			},
			Scopes: []string{"qmt:read"},
		},
		&oauth2.Token{
			AccessToken:  "old-access",
			RefreshToken: "old-refresh",
			TokenType:    "Bearer",
			Expiry:       time.Now().Add(-time.Hour),
		},
		"preregistered",
	); err != nil {
		t.Fatal(err)
	}

	var stdout, stderr bytes.Buffer
	code := Run(
		[]string{"--url", server.URL + "/mcp", "--auth-store", path, "--json", "health"},
		&stdout,
		&stderr,
	)
	if code != 0 {
		t.Fatalf("exit %d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
	}
	if tokenRequests != 1 {
		t.Fatalf("token requests = %d", tokenRequests)
	}
	_, refreshed, _, err := store.Load(server.URL + "/mcp")
	if err != nil {
		t.Fatal(err)
	}
	if refreshed.AccessToken != "new-access" || refreshed.RefreshToken != "new-refresh" {
		t.Fatalf("refreshed token was not persisted: %#v", refreshed)
	}
}
