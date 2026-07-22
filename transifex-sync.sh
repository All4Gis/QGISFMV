#!/bin/bash
# Transifex CLI wrapper for QGIS FMV translations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  pull      Download translations from Transifex"
    echo "  push      Upload source strings to Transifex"
    echo "  push-translations  Upload translations to Transifex"
    echo "  sync      Push source then pull translations"
    echo "  status    Show translation status"
    echo ""
    echo "Default (no command): push source then pull translations"
}

check_tx_installed() {
    # Check local tx binary first, then system-wide
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -x "$SCRIPT_DIR/tx" ]; then
        export PATH="$SCRIPT_DIR:$PATH"
    elif ! command -v tx &> /dev/null; then
        echo -e "${RED}Error: tx (Transifex CLI) is not installed${NC}"
        echo "Install: curl -o- https://raw.githubusercontent.com/transifex/cli/master/install.sh | bash"
        echo "Or place the tx binary in the project root."
        exit 1
    fi
}

check_token() {
    if [ -z "$TX_TOKEN" ] && [ ! -f "$HOME/.transifexrc" ]; then
        echo -e "${YELLOW}Warning: No Transifex token found${NC}"
        echo "Set TX_TOKEN environment variable or create ~/.transifexrc"
        echo ""
    fi
}

pull_translations() {
    echo -e "${GREEN}Downloading translations from Transifex...${NC}"
    if tx pull -a -f --skip; then
        echo -e "${GREEN}Translations updated successfully!${NC}"
    else
        echo -e "${RED}Failed to pull translations${NC}"
        exit 1
    fi
}

push_source() {
    echo -e "${GREEN}Uploading source strings to Transifex...${NC}"
    if tx push -s --skip; then
        echo -e "${GREEN}Source strings uploaded successfully!${NC}"
    else
        echo -e "${RED}Failed to push source strings${NC}"
        exit 1
    fi
}

push_translations() {
    echo -e "${GREEN}Uploading translations to Transifex...${NC}"
    if tx push -t --skip; then
        echo -e "${GREEN}Translations uploaded successfully!${NC}"
    else
        echo -e "${RED}Failed to push translations${NC}"
        exit 1
    fi
}

show_status() {
    echo -e "${GREEN}Translation status:${NC}"
    tx status
}

# Main
check_tx_installed
check_token

case "${1:-sync}" in
    pull)
        pull_translations
        ;;
    push)
        push_source
        ;;
    push-translations)
        push_translations
        ;;
    sync)
        push_source
        pull_translations
        ;;
    status)
        show_status
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        echo -e "${YELLOW}Unknown command: $1${NC}"
        usage
        exit 1
        ;;
esac
