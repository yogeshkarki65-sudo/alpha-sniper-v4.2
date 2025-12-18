#!/bin/bash
# fetch_coderabbit_report.sh
# Fetches CodeRabbit PR review comments from GitHub and saves to markdown file
#
# Usage:
#   ./scripts/fetch_coderabbit_report.sh OWNER REPO PR_NUMBER
#
# Example:
#   ./scripts/fetch_coderabbit_report.sh yogeshkarki65-sudo alpha-sniper-v4.2 123
#
# Output:
#   /opt/alpha-sniper/reports/coderabbit_pr_<PR>.md
#
# Requirements:
#   - gh CLI installed (preferred) OR
#   - curl + GITHUB_TOKEN env var

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
if [ "$#" -ne 3 ]; then
    echo -e "${RED}Error: Invalid arguments${NC}"
    echo "Usage: $0 OWNER REPO PR_NUMBER"
    echo "Example: $0 yogeshkarki65-sudo alpha-sniper-v4.2 123"
    exit 1
fi

OWNER="$1"
REPO="$2"
PR_NUMBER="$3"

# Output directory
REPORTS_DIR="/opt/alpha-sniper/reports"
OUTPUT_FILE="${REPORTS_DIR}/coderabbit_pr_${PR_NUMBER}.md"

# Create reports directory if it doesn't exist
echo -e "${BLUE}Creating reports directory...${NC}"
mkdir -p "$REPORTS_DIR"

# Function to fetch using gh CLI (preferred method)
fetch_with_gh() {
    echo -e "${BLUE}Fetching PR comments using gh CLI...${NC}"

    # Check if gh is installed
    if ! command -v gh &> /dev/null; then
        echo -e "${YELLOW}gh CLI not found, falling back to curl...${NC}"
        return 1
    fi

    # Fetch PR details
    PR_TITLE=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json title --jq '.title' 2>/dev/null || echo "PR #$PR_NUMBER")
    PR_URL=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json url --jq '.url' 2>/dev/null || echo "")

    # Fetch all comments (issue comments + review comments)
    COMMENTS=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json comments --jq '.comments[] | "## Comment by @\(.author.login) - \(.createdAt)\n\n\(.body)\n\n---\n"' 2>/dev/null || echo "")
    REVIEW_COMMENTS=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json reviews --jq '.reviews[] | "## Review by @\(.author.login) - \(.submittedAt)\n\nState: \(.state)\n\n\(.body)\n\n---\n"' 2>/dev/null || echo "")

    # Generate markdown report
    cat > "$OUTPUT_FILE" <<EOF
# CodeRabbit Report - PR #${PR_NUMBER}

**Repository:** ${OWNER}/${REPO}
**Pull Request:** [#${PR_NUMBER}](${PR_URL})
**Title:** ${PR_TITLE}
**Generated:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")

---

## PR Comments

${COMMENTS}

## Review Comments

${REVIEW_COMMENTS}

---

*Report generated using gh CLI*
EOF

    return 0
}

# Function to fetch using GitHub API (fallback method)
fetch_with_api() {
    echo -e "${BLUE}Fetching PR comments using GitHub API...${NC}"

    # Check for GITHUB_TOKEN
    if [ -z "$GITHUB_TOKEN" ]; then
        echo -e "${RED}Error: GITHUB_TOKEN environment variable not set${NC}"
        echo "Set it with: export GITHUB_TOKEN=your_token_here"
        exit 1
    fi

    API_BASE="https://api.github.com"
    PR_URL="${API_BASE}/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}"
    COMMENTS_URL="${API_BASE}/repos/${OWNER}/${REPO}/issues/${PR_NUMBER}/comments"
    REVIEWS_URL="${API_BASE}/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}/reviews"

    # Fetch PR details
    echo -e "${BLUE}Fetching PR details...${NC}"
    PR_DATA=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$PR_URL")
    PR_TITLE=$(echo "$PR_DATA" | grep -o '"title":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "PR #$PR_NUMBER")
    PR_HTML_URL=$(echo "$PR_DATA" | grep -o '"html_url":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")

    # Fetch comments
    echo -e "${BLUE}Fetching PR comments...${NC}"
    COMMENTS_DATA=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$COMMENTS_URL")

    # Fetch reviews
    echo -e "${BLUE}Fetching PR reviews...${NC}"
    REVIEWS_DATA=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$REVIEWS_URL")

    # Generate markdown report (basic version - manual parsing needed for full formatting)
    cat > "$OUTPUT_FILE" <<EOF
# CodeRabbit Report - PR #${PR_NUMBER}

**Repository:** ${OWNER}/${REPO}
**Pull Request:** [#${PR_NUMBER}](${PR_HTML_URL})
**Title:** ${PR_TITLE}
**Generated:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")

---

## PR Comments (Raw JSON)

\`\`\`json
${COMMENTS_DATA}
\`\`\`

## Review Comments (Raw JSON)

\`\`\`json
${REVIEWS_DATA}
\`\`\`

---

*Report generated using GitHub API*
*Note: Use 'gh CLI' for better formatted output*
EOF

    return 0
}

# Main execution
echo -e "${GREEN}=== CodeRabbit Report Fetcher ===${NC}"
echo -e "Owner: ${OWNER}"
echo -e "Repo: ${REPO}"
echo -e "PR: #${PR_NUMBER}"
echo -e "Output: ${OUTPUT_FILE}"
echo ""

# Try gh CLI first, fallback to API
if fetch_with_gh; then
    echo -e "${GREEN}✓ Successfully fetched PR comments using gh CLI${NC}"
elif fetch_with_api; then
    echo -e "${GREEN}✓ Successfully fetched PR comments using GitHub API${NC}"
else
    echo -e "${RED}✗ Failed to fetch PR comments${NC}"
    exit 1
fi

# Display file info
if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null || echo "unknown")
    LINE_COUNT=$(wc -l < "$OUTPUT_FILE")

    echo ""
    echo -e "${GREEN}=== Report Generated ===${NC}"
    echo -e "File: ${OUTPUT_FILE}"
    echo -e "Size: ${FILE_SIZE} bytes"
    echo -e "Lines: ${LINE_COUNT}"
    echo ""
    echo -e "${BLUE}View report:${NC}"
    echo -e "  cat ${OUTPUT_FILE}"
    echo -e "  less ${OUTPUT_FILE}"
    echo ""
    echo -e "${BLUE}Filter for CodeRabbit comments:${NC}"
    echo -e "  grep -i 'coderabbit' ${OUTPUT_FILE}"

    # Check if CodeRabbit bot is mentioned
    if grep -qi 'coderabbit' "$OUTPUT_FILE"; then
        echo ""
        echo -e "${GREEN}✓ CodeRabbit comments found in report${NC}"
    else
        echo ""
        echo -e "${YELLOW}⚠ No CodeRabbit comments detected (may be in different format)${NC}"
    fi
else
    echo -e "${RED}✗ Report file not created${NC}"
    exit 1
fi
