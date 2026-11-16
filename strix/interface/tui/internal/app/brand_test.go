package app

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestBrandDefaultsToUpstream(t *testing.T) {
	t.Setenv("STRIX_BRAND_NAME", "")
	if got := Branded("Quit Strix?"); got != "Quit Strix?" {
		t.Fatalf("Branded() = %q, want upstream text", got)
	}
	if brandBanner() != banner {
		t.Fatal("brandBanner() should be the upstream banner when no brand is set")
	}
}

func TestBrandFromEnvironment(t *testing.T) {
	t.Setenv("STRIX_BRAND_NAME", "Jitera")
	t.Setenv("STRIX_BRAND_URL", "jitera.com")
	if got := Branded("Starting Strix Agent"); got != "Starting Jitera Agent" {
		t.Fatalf("Branded() = %q", got)
	}
	if brandURL() != "jitera.com" {
		t.Fatalf("brandURL() = %q", brandURL())
	}
	if brandBanner() != jiteraBanner {
		t.Fatal("brandBanner() should be the Jitera banner")
	}
}

func TestJiteraBannerMatchesUpstreamShape(t *testing.T) {
	rows := strings.Split(jiteraBanner, "\n")
	if len(rows) != len(strings.Split(banner, "\n")) {
		t.Fatalf("jiteraBanner has %d rows, banner has %d", len(rows), len(strings.Split(banner, "\n")))
	}
	for _, row := range rows {
		if lipgloss.Width(row) == 0 {
			t.Fatal("jiteraBanner has an empty row")
		}
	}
}
