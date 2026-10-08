# Shared helpers for find-ethercat-nic and set-ethercat-nic.
# Sourced, not executed.

# Physical Ethernet ports only. Wi-Fi, bridges, bonds, VLANs, and
# interfaces with no device (veth, docker, tun) are not candidates.
# The port that owns the default route is the shop network, not the
# drive chain. A link-down EtherCAT port is still a candidate: slaves
# often show no carrier until they are powered.

normalize_mac() {
    local mac=${1,,}
    mac=${mac//-/:}
    if [[ ! $mac =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]]; then
        return 1
    fi
    if [[ $mac == 00:00:00:00:00:00 || $mac == ff:ff:ff:ff:ff:ff ]]; then
        return 1
    fi
    printf '%s' "$mac"
}

default_route_ifaces() {
    local family
    for family in -4 -6; do
        ip -o "$family" route show default 2>/dev/null \
            | awk '{for (i = 1; i <= NF; i++) if ($i == "dev") print $(i + 1)}'
    done
}

classify_iface() {
    local iface=$1
    local path="/sys/class/net/${iface}"
    local typ

    if [[ -d ${path}/wireless || -d ${path}/phy80211 ]]; then
        printf 'wireless'
        return
    fi
    if [[ -d ${path}/bridge || -d ${path}/bonding || -d ${path}/vlan ]]; then
        printf 'virtual'
        return
    fi
    if [[ ! -e ${path}/device ]]; then
        printf 'virtual'
        return
    fi
    typ=$(cat "${path}/type" 2>/dev/null || printf '0')
    if [[ $typ == 1 ]]; then
        printf 'ethernet'
        return
    fi
    printf 'other'
}

scan_nics() {
    local iface path mac carrier kind is_default defaults
    defaults=" $(default_route_ifaces | tr '\n' ' ') "
    for path in /sys/class/net/*; do
        [[ -e $path ]] || continue
        iface=$(basename "$path")
        [[ $iface == lo ]] && continue
        [[ -r ${path}/address ]] || continue
        mac=$(cat "${path}/address")
        mac=$(normalize_mac "$mac") || continue
        kind=$(classify_iface "$iface")
        carrier=0
        if [[ -r ${path}/carrier ]]; then
            carrier=$(cat "${path}/carrier" 2>/dev/null || printf '0')
        fi
        [[ $carrier == 1 ]] || carrier=0
        is_default=0
        if [[ $defaults == *" ${iface} "* ]]; then
            is_default=1
        fi
        printf '%s\t%s\t%s\t%s\t%s\n' "$iface" "$mac" "$carrier" "$is_default" "$kind"
    done
}

load_nics() {
    if [[ -n ${ETHERCAT_NIC_FIXTURE:-} ]]; then
        NIC_TABLE=$(grep -v '^[[:space:]]*#' "$ETHERCAT_NIC_FIXTURE" | grep -v '^[[:space:]]*$' || true)
    else
        NIC_TABLE=$(scan_nics)
    fi
}

print_nic_table() {
    local iface mac carrier is_default kind link def
    printf '%-16s %-18s %-6s %-9s %s\n' IFACE MAC LINK DEFAULT KIND
    while IFS=$'\t' read -r iface mac carrier is_default kind; do
        [[ -n $iface ]] || continue
        if [[ $carrier == 1 ]]; then
            link=yes
        else
            link=no
        fi
        if [[ $is_default == 1 ]]; then
            def=yes
        else
            def=no
        fi
        printf '%-16s %-18s %-6s %-9s %s\n' "$iface" "$mac" "$link" "$def" "$kind"
    done <<<"$NIC_TABLE"
}

# Sets CHOSEN_IFACE, CHOSEN_MAC, CHOSEN_REASON. Returns 0 or 2.
choose_from_table() {
    local iface_req=${1:-}
    local mac_req=${2:-}
    local allow_default=${3:-0}
    local iface mac carrier is_default kind
    local -a dedicated=()
    local -a dedicated_desc=()

    CHOSEN_IFACE=
    CHOSEN_MAC=
    CHOSEN_REASON=

    if [[ -n $mac_req ]]; then
        mac_req=$(normalize_mac "$mac_req") || {
            printf 'MAC must look like 00:11:22:33:44:55\n' >&2
            return 2
        }
    fi

    while IFS=$'\t' read -r iface mac carrier is_default kind; do
        [[ -n $iface ]] || continue
        [[ $kind == ethernet ]] || continue

        if [[ -n $iface_req && $iface == "$iface_req" ]]; then
            if [[ $is_default == 1 && $allow_default != 1 ]]; then
                printf '%s owns the default route. Pass --allow-default-route to use it.\n' "$iface" >&2
                return 2
            fi
            CHOSEN_IFACE=$iface
            CHOSEN_MAC=$mac
            CHOSEN_REASON="requested by --iface"
            return 0
        fi
        if [[ -n $mac_req && $mac == "$mac_req" ]]; then
            if [[ $is_default == 1 && $allow_default != 1 ]]; then
                printf '%s (%s) owns the default route. Pass --allow-default-route to use it.\n' "$iface" "$mac" >&2
                return 2
            fi
            CHOSEN_IFACE=$iface
            CHOSEN_MAC=$mac
            CHOSEN_REASON="requested by --mac"
            return 0
        fi
        if [[ -z $iface_req && -z $mac_req && $is_default == 0 ]]; then
            dedicated+=("$iface"$'\t'"$mac")
            dedicated_desc+=("$iface $mac")
        fi
    done <<<"$NIC_TABLE"

    if [[ -n $iface_req ]]; then
        printf 'No physical Ethernet interface named %s\n' "$iface_req" >&2
        return 2
    fi
    if [[ -n $mac_req ]]; then
        printf 'No physical Ethernet interface has MAC %s\n' "$mac_req" >&2
        return 2
    fi

    if [[ ${#dedicated[@]} -eq 1 ]]; then
        CHOSEN_IFACE=${dedicated[0]%%$'\t'*}
        CHOSEN_MAC=${dedicated[0]#*$'\t'}
        CHOSEN_REASON="only Ethernet port that is not the default route"
        return 0
    fi
    if [[ ${#dedicated[@]} -eq 0 ]]; then
        printf 'Every physical Ethernet port owns the default route.\n' >&2
        printf 'Pass --iface NAME --allow-default-route to use one anyway.\n' >&2
        return 2
    fi
    printf 'More than one Ethernet port is free of the default route:\n' >&2
    printf '  %s\n' "${dedicated_desc[@]}" >&2
    printf 'Re-run with --iface NAME. Link state is shown in the table above.\n' >&2
    return 2
}

get_conf_var() {
    local file=$1 key=$2 line val
    while IFS= read -r line || [[ -n $line ]]; do
        line=${line%$'\r'}
        if [[ $line =~ ^[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)$ ]]; then
            val=${BASH_REMATCH[1]}
            val=${val%%#*}
            val="${val%"${val##*[![:space:]]}"}"
            val="${val#"${val%%[![:space:]]*}"}"
            val=${val#\"}
            val=${val%\"}
            val=${val#\'}
            val=${val%\'}
            printf '%s' "$val"
            return 0
        fi
    done <"$file"
    return 1
}

set_conf_var() {
    local file=$1 key=$2 value=$3
    local tmp line found=0
    tmp=$(mktemp "${file}.tmp.XXXXXX")
    while IFS= read -r line || [[ -n $line ]]; do
        line=${line%$'\r'}
        if [[ $found -eq 0 && $line =~ ^[[:space:]]*${key}[[:space:]]*= ]]; then
            printf '%s="%s"\n' "$key" "$value"
            found=1
        else
            printf '%s\n' "$line"
        fi
    done <"$file" >"$tmp"
    if [[ $found -eq 0 ]]; then
        printf '\n%s="%s"\n' "$key" "$value" >>"$tmp"
    fi
    cat "$tmp" >"$file"
    rm -f "$tmp"
}

apply_master_device() {
    local file=$1 iface=$2 mac=$3
    local modules
    set_conf_var "$file" MASTER0_DEVICE "$mac"
    modules=$(get_conf_var "$file" DEVICE_MODULES || true)
    if [[ -z $modules ]]; then
        set_conf_var "$file" DEVICE_MODULES "generic"
        modules=generic
    fi
    if [[ " $modules " == *" generic "* ]]; then
        set_conf_var "$file" UPDOWN_INTERFACES "$iface"
    fi
}
