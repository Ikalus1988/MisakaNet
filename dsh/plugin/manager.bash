#!/usr/bin/env bash
# dsh.plugin.manager.bash - Plugin manager with profile-aware installation

dsh_plugin_resolve_profile() {
    local requested_profile="${1:-}"

    # Enumerate actual profiles from disk
    local profiles_dir="${DSH_HOME:-$HOME/.dsh}/profiles"
    if [[ ! -d "$profiles_dir" ]]; then
        echo "desktop"
        return 0
    fi

    local -a actual_profiles=()
    local entry
    for entry in "$profiles_dir"/*/; do
        [[ -d "$entry" ]] || continue
        local pname
        pname="$(basename "$entry")"
        actual_profiles+=("$pname")
    done

    # Determine which profile the running host actually consumes
    local running_profile=""
    # Check DSH_PROFILE env first
    if [[ -n "$DSH_PROFILE" ]]; then
        running_profile="$DSH_PROFILE"
    fi

    # Fall back to default profile file if exists
    if [[ -z "$running_profile" && -f "${profiles_dir}/.default" ]]; then
        running_profile="$(cat "${profiles_dir}/.default" 2>/dev/null)"
    fi

    # Fall back to the only profile present
    if [[ -z "$running_profile" && ${#actual_profiles[@]} -eq 1 ]]; then
        running_profile="${actual_profiles[0]}"
    fi

    # If a profile was explicitly requested, validate it against the host's profiles
    if [[ -n "$requested_profile" ]]; then
        local found=0
        for p in "${actual_profiles[@]}"; do
            if [[ "$p" == "$requested_profile" ]]; then
                found=1
                break
            fi
        done
        if [[ $found -eq 0 ]]; then
            echo "WARNING: Profile '$requested_profile' does not exist on this host. Available profiles: ${actual_profiles[*]}" >&2
            echo "Using running host profile: ${running_profile:-${actual_profiles[0]:-desktop}}" >&2
            if [[ -n "$running_profile" ]]; then
                echo "$running_profile"
            elif [[ ${#actual_profiles[@]} -gt 0 ]]; then
                echo "${actual_profiles[0]}"
            else
                echo "desktop"
            fi
            return 1
        fi
        echo "$requested_profile"
        return 0
    fi

    # No profile requested — return the running host's profile
    if [[ -n "$running_profile" ]]; then
        echo "$running_profile"
    elif [[ ${#actual_profiles[@]} -gt 0 ]]; then
        echo "${actual_profiles[0]}"
    else
        echo "desktop"
    fi
}

dsh_plugin_install() {
    local plugin_name="${1:?Plugin name required}"
    local requested_profile="${2:-}"

    # Resolve the actual profile instead of blindly using whatever the README says
    local profile
    profile="$(dsh_plugin_resolve_profile "$requested_profile")"

    local profiles_dir="${DSH_HOME:-$HOME/.dsh}/profiles"
    local profile_dir="${profiles_dir}/${profile}"
    local bundles_file="${profile_dir}/dsh.profile.bundles"

    mkdir -p "$profile_dir"

    # Install the plugin bundle into the resolved profile directory
    local bundle_dir="${profile_dir}/bundles/${plugin_name}"
    mkdir -p "$bundle_dir"

    # Pull plugin sources (simplified — adapt to your actual fetch mechanism)
    local repo_url="https://github.com/dsh-plugins/${plugin_name}.git"
    if command -v git &>/dev/null; then
        rm -rf "${bundle_dir}-tmp"
        git clone --depth 1 "$repo_url" "${bundle_dir}-tmp" 2>/dev/null
        if [[ $? -eq 0 && -d "${bundle_dir}-tmp" ]]; then
            mv "${bundle_dir}-tmp" "$bundle_dir"
        else
            echo "ERROR: Failed to clone plugin '${plugin_name}' from ${repo_url}" >&2
            rm -rf "${bundle_dir}-tmp"
            return 1
        fi
    else
        echo "ERROR: git is required to install plugins" >&2
        return 1
    fi

    # Record the bundle in the profile's bundles manifest
    if [[ -f "$bundles_file" ]]; then
        grep -qxF "$plugin_name" "$bundles_file" || echo "$plugin_name" >> "$bundles_file"
    else
        echo "$plugin_name" > "$bundles_file"
    fi

    echo "Plugin '${plugin_name}' installed into profile '${profile}'"
    echo "Bundle manifest: ${bundles_file}"

    # Verify components are present
    local has_tools=0
    if ls "${bundle_dir}"/bin/* &>/dev/null || ls "${bundle_dir}"/tools/* &>/dev/null; then
        has_tools=1
    fi
    if [[ $has_tools -eq 1 ]]; then
        echo "VERIFIED: Plugin tools are present in the running host profile."
    else
        echo "WARNING: No bin/tools directory found in ${bundle_dir}" >&2
    fi
}

# When sourced as a library, expose functions; when run directly, handle CLI
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        install)
            shift
            dsh_plugin_install "$@"
            ;;
        list)
            local profiles_dir="${DSH_HOME:-$HOME/.dsh}/profiles"
            echo "Available profiles:"
            for entry in "$profiles_dir"/*/; do
                [[ -d "$entry" ]] || continue
                echo "  - $(basename "$entry")"
            done
            ;;
        *)
            echo "Usage: dsh.plugin.manager.bash {install <name> [profile]|list}" >&2
            exit 1
            ;;
    esac
fi
