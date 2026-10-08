#!/usr/bin/env bash
# Selection and ethercat.conf rewrite checks. No root and no live NIC.

set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=nic-common.sh
source "${here}/nic-common.sh"

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

write_fixture() {
    printf '%s\n' "$@" >"${tmp}/nics"
    ETHERCAT_NIC_FIXTURE=${tmp}/nics
    load_nics
}

assert_choice() {
    local iface=$1 mac=$2
    choose_from_table "${3:-}" "${4:-}" "${5:-0}" || fail "expected a choice, got none"
    [[ $CHOSEN_IFACE == "$iface" ]] || fail "iface $CHOSEN_IFACE != $iface"
    [[ $CHOSEN_MAC == "$mac" ]] || fail "mac $CHOSEN_MAC != $mac"
}

assert_refuse() {
    if choose_from_table "${1:-}" "${2:-}" "${3:-0}" 2>/dev/null; then
        fail "expected refusal, chose $CHOSEN_IFACE"
    fi
}

# iface mac carrier default kind
write_fixture \
    $'enp1s0\taa:bb:cc:dd:ee:01\t1\t1\tethernet' \
    $'enp2s0\taa:bb:cc:dd:ee:02\t0\t0\tethernet' \
    $'wlp3s0\taa:bb:cc:dd:ee:03\t1\t0\twireless' \
    $'docker0\taa:bb:cc:dd:ee:04\t0\t0\tvirtual'
assert_choice enp2s0 aa:bb:cc:dd:ee:02
[[ $CHOSEN_REASON == "only Ethernet port that is not the default route" ]] || fail "reason: $CHOSEN_REASON"

write_fixture \
    $'enp1s0\taa:bb:cc:dd:ee:01\t1\t1\tethernet'
assert_refuse
assert_refuse "" "" 1
assert_choice enp1s0 aa:bb:cc:dd:ee:01 enp1s0 "" 1

write_fixture \
    $'enp1s0\taa:bb:cc:dd:ee:01\t1\t1\tethernet' \
    $'enp2s0\taa:bb:cc:dd:ee:02\t0\t0\tethernet' \
    $'enp3s0\taa:bb:cc:dd:ee:03\t1\t0\tethernet'
assert_refuse
assert_choice enp3s0 aa:bb:cc:dd:ee:03 enp3s0

write_fixture \
    $'enp2s0\taa:bb:cc:dd:ee:02\t0\t0\tethernet'
assert_choice enp2s0 aa:bb:cc:dd:ee:02 "" AA-BB-CC-DD-EE-02

normalize_mac "AA-BB-CC-DD-EE-02" >/dev/null || fail "normalize dashed MAC"
if normalize_mac "ff:ff:ff:ff:ff:ff"; then
    fail "broadcast MAC should be rejected"
fi

sample=$(cat <<'EOF'
# MASTER0_DEVICE="ff:ff:ff:ff:ff:ff"
MASTER0_DEVICE=""
#MASTER1_DEVICE=""
DEVICE_MODULES=""
UPDOWN_INTERFACES=""
EOF
)
printf '%s\n' "$sample" >"${tmp}/ethercat.conf"
apply_master_device "${tmp}/ethercat.conf" enp2s0 aa:bb:cc:dd:ee:02
[[ $(get_conf_var "${tmp}/ethercat.conf" MASTER0_DEVICE) == aa:bb:cc:dd:ee:02 ]] || fail "MASTER0_DEVICE"
[[ $(get_conf_var "${tmp}/ethercat.conf" DEVICE_MODULES) == generic ]] || fail "DEVICE_MODULES"
[[ $(get_conf_var "${tmp}/ethercat.conf" UPDOWN_INTERFACES) == enp2s0 ]] || fail "UPDOWN"
grep -q '^#MASTER1_DEVICE=""$' "${tmp}/ethercat.conf" || fail "MASTER1 comment changed"
grep -q '^# MASTER0_DEVICE=' "${tmp}/ethercat.conf" || fail "commented MASTER0 changed"

apply_master_device "${tmp}/ethercat.conf" enp2s0 aa:bb:cc:dd:ee:09
[[ $(get_conf_var "${tmp}/ethercat.conf" MASTER0_DEVICE) == aa:bb:cc:dd:ee:09 ]] || fail "second write"
[[ $(grep -c '^MASTER0_DEVICE=' "${tmp}/ethercat.conf") -eq 1 ]] || fail "duplicate MASTER0"

printf 'DEVICE_MODULES="igb"\nUPDOWN_INTERFACES=""\nMASTER0_DEVICE=""\n' >"${tmp}/native.conf"
apply_master_device "${tmp}/native.conf" enp4s0 11:22:33:44:55:66
[[ $(get_conf_var "${tmp}/native.conf" DEVICE_MODULES) == igb ]] || fail "native module overwritten"
[[ -z $(get_conf_var "${tmp}/native.conf" UPDOWN_INTERFACES) ]] || fail "UPDOWN set for native driver"

unset ETHERCAT_NIC_FIXTURE
load_nics
[[ -n $NIC_TABLE || -z $NIC_TABLE ]] || fail "live scan crashed"

printf 'ok\n'
