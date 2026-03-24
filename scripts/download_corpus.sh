#!/usr/bin/env bash
# Download documentation from 10 repos in parallel using sparse-checkout.
# If the expected docs path is empty, tries common alternatives.
# Keeps only .md and .pdf files, removes everything else.

set -euo pipefail

CORPUS_DIR="$(cd "$(dirname "$0")/.." && pwd)/docs/corpus"
TEMP_DIR=$(mktemp -d)
LOG_DIR=$(mktemp -d)

echo "Corpus dir: $CORPUS_DIR"
echo "Temp dir:   $TEMP_DIR"
echo "=========================================="

clone_docs() {
    local repo="$1"
    local doc_path="$2"
    local dest_name="$3"
    local alt_paths="$4"
    local log_file="$LOG_DIR/${dest_name}.log"
    local clone_dir="$TEMP_DIR/$dest_name"
    local dest_dir="$CORPUS_DIR/$dest_name"

    {
        echo "[$dest_name] Starting clone of $repo (path: $doc_path)"

        # Sparse checkout clone
        git clone --filter=blob:none --no-checkout --depth 1 \
            "https://github.com/${repo}.git" "$clone_dir" 2>&1

        cd "$clone_dir"
        git sparse-checkout init --cone 2>&1
        git sparse-checkout set "$doc_path" 2>&1
        git checkout 2>&1

        # Check if path has content
        local found_path=""
        if [ -d "$clone_dir/$doc_path" ] && [ "$(find "$clone_dir/$doc_path" -type f 2>/dev/null | head -1)" ]; then
            found_path="$doc_path"
        else
            echo "[$dest_name] Primary path '$doc_path' empty, trying alternatives..."
            IFS=',' read -ra alts <<< "$alt_paths"
            for alt in "${alts[@]}"; do
                alt=$(echo "$alt" | xargs)  # trim whitespace
                [ -z "$alt" ] && continue
                git sparse-checkout set "$alt" 2>&1
                git checkout 2>&1 || true
                if [ -d "$clone_dir/$alt" ] && [ "$(find "$clone_dir/$alt" -type f 2>/dev/null | head -1)" ]; then
                    found_path="$alt"
                    echo "[$dest_name] Found docs at alternative path: $alt"
                    break
                fi
            done
        fi

        if [ -z "$found_path" ]; then
            echo "[$dest_name] FAILED — no docs found at any path"
            echo "FAILED" > "$LOG_DIR/${dest_name}.status"
            return 1
        fi

        echo "[$dest_name] Using path: $found_path"

        # Copy to corpus
        mkdir -p "$dest_dir"
        cp -R "$clone_dir/$found_path"/. "$dest_dir/" 2>&1

        # Remove non-doc files (keep only .md and .pdf)
        find "$dest_dir" -type f \
            ! -name '*.md' \
            ! -name '*.pdf' \
            -delete 2>&1

        # Remove empty directories
        find "$dest_dir" -type d -empty -delete 2>/dev/null || true

        # Remove any .git remnants
        rm -rf "$dest_dir/.git" 2>/dev/null || true

        # Count results
        local md_count=$(find "$dest_dir" -name '*.md' -type f | wc -l | xargs)
        local pdf_count=$(find "$dest_dir" -name '*.pdf' -type f | wc -l | xargs)
        local total_size=$(du -sh "$dest_dir" 2>/dev/null | cut -f1 | xargs)

        echo "[$dest_name] DONE — $md_count .md, $pdf_count .pdf, $total_size total"
        echo "OK|$md_count|$pdf_count|$total_size" > "$LOG_DIR/${dest_name}.status"

    } > "$log_file" 2>&1
}

# Launch all 10 in parallel
# Format: repo doc_path dest_name alt_paths

clone_docs "langchain-ai/langchain"   "docs/docs"       "langchain"   "docs,docs/src"       &
clone_docs "fastapi/fastapi"          "docs/en/docs"    "fastapi"     "docs/en,docs"        &
clone_docs "pydantic/pydantic"        "docs"            "pydantic"    "docs/docs"           &
clone_docs "chroma-core/chroma"       "docs"            "chromadb"    "docs/docs"           &
clone_docs "langfuse/langfuse-docs"   "pages/docs"      "langfuse"    "pages,docs,src/pages" &
clone_docs "reactjs/react.dev"        "src/content"     "react"       "content,docs"        &
clone_docs "docker/docs"              "content"         "docker"      "docs"                &
clone_docs "kubernetes/website"       "content/en/docs" "kubernetes"  "content/en,docs"     &
clone_docs "hashicorp/terraform"      "website/docs"    "terraform"   "website,docs"        &
clone_docs "git/git"                  "Documentation"   "git"         "doc,docs"            &

echo "All 10 downloads launched in parallel. Waiting..."
wait
echo ""
echo "=========================================="
echo "RESULTS SUMMARY"
echo "=========================================="

failed=()
for dest_name in langchain fastapi pydantic chromadb langfuse react docker kubernetes terraform git; do
    status_file="$LOG_DIR/${dest_name}.status"
    if [ ! -f "$status_file" ]; then
        echo "  $dest_name: FAILED (no status file — check $LOG_DIR/${dest_name}.log)"
        failed+=("$dest_name")
    elif grep -q "^FAILED" "$status_file"; then
        echo "  $dest_name: FAILED — no docs found"
        failed+=("$dest_name")
    else
        IFS='|' read -r _ md_count pdf_count total_size < "$status_file"
        printf "  %-12s: %4s .md, %3s .pdf, %s\n" "$dest_name" "$md_count" "$pdf_count" "$total_size"
    fi
done

echo ""
if [ ${#failed[@]} -gt 0 ]; then
    echo "FAILED repos needing manual attention: ${failed[*]}"
    echo ""
    echo "Logs available at: $LOG_DIR/"
else
    echo "All 10 repos downloaded successfully!"
fi

# Cleanup temp clones
rm -rf "$TEMP_DIR"
echo "Temp clones cleaned up."
echo "Corpus at: $CORPUS_DIR"
