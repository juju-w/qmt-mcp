package qmtctl

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"golang.org/x/oauth2"
)

const oauthStoreVersion = 1

var ErrOAuthSessionNotFound = errors.New("OAuth session not found")

type storedOAuthEndpoint struct {
	AuthURL   string           `json:"auth_url"`
	TokenURL  string           `json:"token_url"`
	AuthStyle oauth2.AuthStyle `json:"auth_style"`
}

type storedOAuthToken struct {
	AccessToken  string    `json:"access_token"`
	TokenType    string    `json:"token_type,omitempty"`
	RefreshToken string    `json:"refresh_token,omitempty"`
	Expiry       time.Time `json:"expiry,omitempty"`
}

type storedOAuthSession struct {
	Resource     string              `json:"resource"`
	ClientID     string              `json:"client_id"`
	Scopes       []string            `json:"scopes,omitempty"`
	Endpoint     storedOAuthEndpoint `json:"endpoint"`
	Token        storedOAuthToken    `json:"token"`
	Registration string              `json:"registration"`
	UpdatedAt    time.Time           `json:"updated_at"`
}

type oauthStoreDocument struct {
	Version  int                           `json:"version"`
	Sessions map[string]storedOAuthSession `json:"sessions"`
}

type oauthSessionStore struct {
	path string
	mu   sync.Mutex
}

func defaultOAuthStorePath() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", fmt.Errorf("resolve user config directory: %w", err)
	}
	return filepath.Join(base, "qmtctl", "oauth-sessions.json"), nil
}

func newOAuthSessionStore(path string) (*oauthSessionStore, error) {
	if strings.TrimSpace(path) == "" {
		var err error
		path, err = defaultOAuthStorePath()
		if err != nil {
			return nil, err
		}
	}
	return &oauthSessionStore{path: path}, nil
}

func canonicalResource(raw string) (string, error) {
	u, err := parseAbsoluteURL(raw)
	if err != nil {
		return "", err
	}
	u.Scheme = strings.ToLower(u.Scheme)
	u.Host = strings.ToLower(u.Host)
	if u.User != nil || u.Fragment != "" {
		return "", errors.New("OAuth resource URL must not contain user info or a fragment")
	}
	if u.Path != "/" {
		u.Path = strings.TrimRight(u.Path, "/")
	}
	return u.String(), nil
}

func (s *oauthSessionStore) Load(resource string) (*oauth2.Config, *oauth2.Token, storedOAuthSession, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	key, err := canonicalResource(resource)
	if err != nil {
		return nil, nil, storedOAuthSession{}, err
	}
	document, err := s.loadUnlocked()
	if err != nil {
		return nil, nil, storedOAuthSession{}, err
	}
	session, ok := document.Sessions[key]
	if !ok {
		return nil, nil, storedOAuthSession{}, ErrOAuthSessionNotFound
	}
	config := &oauth2.Config{
		ClientID: session.ClientID,
		Endpoint: oauth2.Endpoint{
			AuthURL:   session.Endpoint.AuthURL,
			TokenURL:  session.Endpoint.TokenURL,
			AuthStyle: session.Endpoint.AuthStyle,
		},
		Scopes: append([]string(nil), session.Scopes...),
	}
	token := &oauth2.Token{
		AccessToken:  session.Token.AccessToken,
		TokenType:    session.Token.TokenType,
		RefreshToken: session.Token.RefreshToken,
		Expiry:       session.Token.Expiry,
	}
	return config, token, session, nil
}

func (s *oauthSessionStore) Save(
	resource string,
	config *oauth2.Config,
	token *oauth2.Token,
	registration string,
) error {
	if config == nil || token == nil || token.AccessToken == "" {
		return errors.New("cannot save an empty OAuth session")
	}
	if config.ClientSecret != "" {
		return errors.New("qmtctl does not persist OAuth client secrets")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	release, err := s.acquireLock()
	if err != nil {
		return err
	}
	defer release()

	key, err := canonicalResource(resource)
	if err != nil {
		return err
	}
	document, err := s.loadUnlocked()
	if err != nil && !errors.Is(err, ErrOAuthSessionNotFound) {
		return err
	}
	if document.Sessions == nil {
		document = oauthStoreDocument{Version: oauthStoreVersion, Sessions: map[string]storedOAuthSession{}}
	}
	document.Sessions[key] = storedOAuthSession{
		Resource: key,
		ClientID: config.ClientID,
		Scopes:   append([]string(nil), config.Scopes...),
		Endpoint: storedOAuthEndpoint{
			AuthURL:   config.Endpoint.AuthURL,
			TokenURL:  config.Endpoint.TokenURL,
			AuthStyle: config.Endpoint.AuthStyle,
		},
		Token: storedOAuthToken{
			AccessToken:  token.AccessToken,
			TokenType:    token.TokenType,
			RefreshToken: token.RefreshToken,
			Expiry:       token.Expiry,
		},
		Registration: registration,
		UpdatedAt:    time.Now().UTC(),
	}
	return s.writeUnlocked(document)
}

func (s *oauthSessionStore) Delete(resource string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	release, err := s.acquireLock()
	if err != nil {
		return false, err
	}
	defer release()

	key, err := canonicalResource(resource)
	if err != nil {
		return false, err
	}
	document, err := s.loadUnlocked()
	if errors.Is(err, ErrOAuthSessionNotFound) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if _, ok := document.Sessions[key]; !ok {
		return false, nil
	}
	delete(document.Sessions, key)
	return true, s.writeUnlocked(document)
}

func (s *oauthSessionStore) loadUnlocked() (oauthStoreDocument, error) {
	info, err := os.Stat(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return oauthStoreDocument{}, ErrOAuthSessionNotFound
	}
	if err != nil {
		return oauthStoreDocument{}, err
	}
	if runtime.GOOS != "windows" && info.Mode().Perm()&0o077 != 0 {
		return oauthStoreDocument{}, fmt.Errorf("OAuth session store permissions must be 0600: %s", s.path)
	}
	data, err := os.ReadFile(s.path)
	if err != nil {
		return oauthStoreDocument{}, err
	}
	var document oauthStoreDocument
	if err := json.Unmarshal(data, &document); err != nil {
		return oauthStoreDocument{}, fmt.Errorf("decode OAuth session store: %w", err)
	}
	if document.Version != oauthStoreVersion || document.Sessions == nil {
		return oauthStoreDocument{}, errors.New("unsupported OAuth session store format")
	}
	return document, nil
}

func (s *oauthSessionStore) writeUnlocked(document oauthStoreDocument) error {
	dir := filepath.Dir(s.path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	if runtime.GOOS != "windows" {
		if err := os.Chmod(dir, 0o700); err != nil {
			return err
		}
	}
	temp, err := os.CreateTemp(dir, ".oauth-sessions-*")
	if err != nil {
		return err
	}
	tempName := temp.Name()
	defer os.Remove(tempName)
	if err := temp.Chmod(0o600); err != nil {
		temp.Close()
		return err
	}
	encoder := json.NewEncoder(temp)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(document); err != nil {
		temp.Close()
		return err
	}
	if err := temp.Sync(); err != nil {
		temp.Close()
		return err
	}
	if err := temp.Close(); err != nil {
		return err
	}
	return replaceFile(tempName, s.path)
}

func (s *oauthSessionStore) acquireLock() (func(), error) {
	lockPath := s.path + ".lock"
	if err := os.MkdirAll(filepath.Dir(lockPath), 0o700); err != nil {
		return nil, err
	}
	deadline := time.Now().Add(3 * time.Second)
	for {
		file, err := os.OpenFile(lockPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err == nil {
			_ = file.Close()
			return func() { _ = os.Remove(lockPath) }, nil
		}
		if !errors.Is(err, os.ErrExist) {
			return nil, err
		}
		if info, statErr := os.Stat(lockPath); statErr == nil && time.Since(info.ModTime()) > 30*time.Second {
			_ = os.Remove(lockPath)
			continue
		}
		if time.Now().After(deadline) {
			return nil, errors.New("timed out waiting for OAuth session store lock")
		}
		time.Sleep(25 * time.Millisecond)
	}
}

type savingTokenSource struct {
	mu       sync.Mutex
	source   oauth2.TokenSource
	config   *oauth2.Config
	previous storedOAuthToken
	save     func(*oauth2.Config, *oauth2.Token) error
}

func (s *savingTokenSource) Token() (*oauth2.Token, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	token, err := s.source.Token()
	if err != nil {
		return nil, err
	}
	current := storedOAuthToken{
		AccessToken:  token.AccessToken,
		TokenType:    token.TokenType,
		RefreshToken: token.RefreshToken,
		Expiry:       token.Expiry,
	}
	if current != s.previous {
		if err := s.save(s.config, token); err != nil {
			return nil, err
		}
		s.previous = current
	}
	return token, nil
}

func newSavingTokenSource(
	source oauth2.TokenSource,
	config *oauth2.Config,
	initial *oauth2.Token,
	save func(*oauth2.Config, *oauth2.Token) error,
) oauth2.TokenSource {
	previous := storedOAuthToken{}
	if initial != nil {
		previous = storedOAuthToken{
			AccessToken:  initial.AccessToken,
			TokenType:    initial.TokenType,
			RefreshToken: initial.RefreshToken,
			Expiry:       initial.Expiry,
		}
	}
	return &savingTokenSource{source: source, config: config, previous: previous, save: save}
}
