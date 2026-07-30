//go:build !windows

package qmtctl

import "os"

func replaceFile(source, target string) error {
	return os.Rename(source, target)
}
