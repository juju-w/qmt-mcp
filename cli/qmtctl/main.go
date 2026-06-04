package main

import (
	"os"

	"github.com/juju-w/qmt-mcp/cli/qmtctl/internal/qmtctl"
)

func main() {
	os.Exit(qmtctl.Run(os.Args[1:], os.Stdout, os.Stderr))
}
