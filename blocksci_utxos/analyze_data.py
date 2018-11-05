import itertools
import json
import operator
import pickle
from math import sqrt
import numpy as np

from external_apis import *
from constants import *


def flatten_dict_values(d):
    return list(itertools.chain(*d.values()))


def dump_estimations_to_json(coin=BITCOIN, input_type="ALL"):
    """
    Dumps estimation data from pickle_files to json files (that can be loaded into STATUS for computing
    non-profitability metrics).

    :param coin: coin: studied coin
    :param input_type: type of input to dump ("ALL", "P2PKH", "P2SH", "NONSTD" or "P2WSH")
    :return:
    """

    if input_type in ["ALL", "P2PKH"]:

        pickle_file = COIN_STR[coin] + "_pk_sizes_out"

        def avg_from_dict(d):
            avg_pksize = 0
            counter = 0
            for k, v in d.items():
                avg_pksize += k * v
                counter += v

            return avg_pksize / float(counter) if counter != 0 else np.nan

        (pubkey_sizes_outs, unknowns_outs) = pickle.load(open(pickle_file+".pickle", "rb"))
        p2pkh_pubkey_avg_size_height_output = {}
        last_not_nan = 65
        for k, v in pubkey_sizes_outs.items():
            avg = avg_from_dict(v)
            if not np.isnan(avg):
                last_not_nan = avg

            p2pkh_pubkey_avg_size_height_output[k] = last_not_nan

        f = open(COIN_STR[coin]+"_p2pkh_pubkey_avg_size_height_output.json", "w")
        f.write(json.dumps(p2pkh_pubkey_avg_size_height_output))
        f.close()

    if input_type in ["ALL", "P2SH"]:
        pickle_file = COIN_STR[coin] + "_p2sh"
        (p2sh, others_in_p2sh) = pickle.load(open(pickle_file + ".pickle", "rb"))
        avg_per_type, std_per_type, avg_abs, std_abs, avg_per_height = p2sh_average_size(p2sh)
        f = open(COIN_STR[coin]+"_p2sh.json", "w")
        f.write(json.dumps(avg_abs))
        f.close()

    if input_type in ["ALL", "NONSTD"]:

        pickle_file = COIN_STR[coin] + "_non_std_inputs"

        # Legacy code: DELETE when bitcoin non-std has been analyzed with the new code!!
        # (scripts) = pickle.load(open(pickle_file+".pickle", "rb"))
        # script_lens = {k: [int(len(e) / 2) for e in v] for k, v in scripts.items()}
        # flatt_lens = flatten_dict_values(script_lens)
        # print("The average non-std input script len. is: {}".format(np.mean(flatt_lens)))

        # New code:
        (nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens) = pickle.load(open(pickle_file+".pickle", "rb"))
        flatt_lens = flatten_dict_values(nonstd_sizes_lens)
        non_std_mean = np.mean(flatt_lens)
        f = open(COIN_STR[coin]+"_nonstd.json", "w")
        f.write(json.dumps(non_std_mean))
        f.close()

    if input_type in ["ALL", "P2WSH"]:
        pickle_file = COIN_STR[coin] + "_p2wsh_inputs"
        (p2wsh_sizes_outs, p2wsh_sizes_scripts, p2wsh_sizes_lens) = pickle.load(open(pickle_file + ".pickle", "rb"))
        flatt_lens = flatten_dict_values(p2wsh_sizes_lens)
        p2wsh_mean = np.mean(flatt_lens)
        f = open(COIN_STR[coin]+"_p2wsh.json", "w")
        f.write(json.dumps(p2wsh_mean))
        f.close()


def p2sh_compute_script_size(v, ty):
    """
    Given a type 'ty' and the value 'v' stored by blocksci_find_p2shinputs for that type, we compute the estimated
    input length.

    :param v: values stored by blocksci_find_p2shinputs (the exact meaning depends on the type)
    :param ty: script type
    :return: input script size (redeem script + data)
    """
    if ty == "multisig":
        (n, m) = v
        # OP_0 | (PUSH SIG | SIG )*n |
        # PUSH SCRIPT | M | (PUSH PK | PK )*m | N | OP_CHECKMULTISIG
        return 1 + (1 + 71) * n + 1 + (1 + 33) * m + 1 + 1

    if ty == "nonstandard":
        return v

    if ty == "pubkey":
        # PUSH SIG | SIG |
        # PUSH SCRIPT | PUSH PK | PK | OP_CHECKSIG
        return 1 + 71 + 1 + 1 + v + 1

    if ty == "pubkeyhash":
        # PUSH SIG | SIG | PUSH PK | PK
        # PUSH SCRIPT | OP_DUP | OP_HASH160 | PUSH HASH | HASH | OP_EQUALVERIFY | OP_CHECKSIG
        return 1 + 71 + 1 + 33 + 1 + 1 + 1 + 1 + 20 + 1 + 1

    if ty == "scripthash":
        # Empirical value obtained from P2SH scripts found inside P2SH scripts (blockchain.info API)
        # PUSH DATA | DATA | PUSH SCRIPT | P2SH output
        # ? + ? + 1 + 23
        # We have found 82 scripts: in 80 of them, ?+? = 1; in 2 of them ?+?= 154
        return v #28.73

    if ty == "P2WPKH":
        return 23

    if ty == "P2WSH":
        return 35

    if ty == "Others":
        return float('nan')


def p2sh_agg_height_dict(p2sh):
    """
    Aggregates a p2sh dictionary (as stored by blocksci_find_p2shinputs), omitting info about block height.

    :param p2sh: dictionary with block height as keys
    :return: dictionary with script types as keys
    """

    r = {"multisig": {}, 'nonstandard': {}, 'pubkey': {}, "pubkeyhash": {}, "scripthash": {},
         "P2WPKH": 0, "P2WSH": 0, "others": 0}

    for h, v in p2sh.items():
        for ty, ctr in v.items():
            if type(ctr) == dict:
                for inner_dict_k, inner_dict_v in ctr.items():
                    if inner_dict_k in r[ty].keys():
                        r[ty][inner_dict_k] += inner_dict_v
                    else:
                        r[ty][inner_dict_k] = inner_dict_v
            else:
                r[ty] += ctr

    return r


def p2sh_average_size(p2sh, with_vectors=False):
    """
    Aggregates P2SH data by type and height, and computes overall averages.

    :param p2sh:
    :param with_vectors:
    :return:
    """

    agg_data = p2sh_agg_height_dict(p2sh)

    assert agg_data["others"] == 0
    del agg_data["others"]

    ###################################################
    # average per type
    ###################################################

    avg_per_type = {}
    std_per_type = {}

    if with_vectors:
        # slower, but nice to check the other implementation ;)

        non = [v * [k] for k, v in agg_data["nonstandard"].items()]
        merged = list(itertools.chain(*non))
        np.mean(merged)
        np.std(merged)
    else:
        for in_type, data_dict in agg_data.items():
            if type(data_dict) == dict:
                ctr = 0
                type_average = 0
                for k, v in data_dict.items():
                    type_average += v * p2sh_compute_script_size(k, in_type)
                    ctr += v
                avg_per_type[in_type] = type_average / float(ctr)
            else:
                avg_per_type[in_type] = p2sh_compute_script_size(None, in_type)

        for in_type, data_dict in agg_data.items():
            if type(data_dict) == dict:
                ctr = 0
                type_std = 0
                for k, v in data_dict.items():
                    type_std += v * pow((p2sh_compute_script_size(k, in_type) - avg_per_type[in_type]), 2)
                    ctr += v
                std_per_type[in_type] = sqrt(type_std / float(ctr - 1))
            else:
                std_per_type[in_type] = 0

    ###################################################
    # overall average
    ###################################################
    avg_abs = 0
    std_abs = 0
    ctr = 0
    for in_type, data_dict in agg_data.items():
        if type(data_dict) == dict:
            for k, v in data_dict.items():
                avg_abs += v * p2sh_compute_script_size(k, in_type)
                ctr += v
        else:
            avg_abs += data_dict * p2sh_compute_script_size(None, in_type)
            ctr += data_dict
    avg_abs = avg_abs / float(ctr)

    for in_type, data_dict in agg_data.items():
        if type(data_dict) == dict:
            for k, v in data_dict.items():
                std_abs += v * pow((p2sh_compute_script_size(k, in_type) - avg_abs), 2)
        else:
            std_abs += data_dict * pow((p2sh_compute_script_size(None, in_type) - avg_abs), 2)

    std_abs = sqrt(std_abs / float(ctr - 1))


    ###################################################
    # average per height?
    ###################################################

    avg_per_height = {}
    for h, v in p2sh.items():
        this_height_avg = 0
        ctr = 0
        for in_type, data_dict in v.items():
            if in_type == "others":
                pass
            elif type(data_dict) == dict:
                for k, v in data_dict.items():
                    this_height_avg += v * p2sh_compute_script_size(k, in_type)
                    ctr += v
            else:
                this_height_avg += data_dict * p2sh_compute_script_size(None, in_type)
                ctr += data_dict

        if ctr:
            avg_per_height[h] = this_height_avg/ctr
        else:
            avg_per_height[h] = np.nan

    #pickle.dump((avg_per_height), open("p2sh_avg_per_height.pickle", "wb"))
    return avg_per_type, std_per_type, avg_abs, std_abs, avg_per_height


def p2sh_num_inputs_per_redeem_script_type(p2sh):
    """
    Prints a summary of script types nested in P2SH inputs

    :param p2sh: p2sh dictionary, as created by blocksci_find_p2sh_inputs function
    :return:
    """

    num_multisig = sum([sum(h_v["multisig"].values()) for h_v in p2sh.values()])
    num_nonstd = sum([sum(h_v["nonstandard"].values()) for h_v in p2sh.values()])
    num_pubkey = sum([sum(h_v["pubkey"].values()) for h_v in p2sh.values()])
    num_pubkeyhash = sum([sum(h_v["pubkeyhash"].values()) for h_v in p2sh.values()])
    num_scripthash = sum([sum(h_v["scripthash"].values()) for h_v in p2sh.values()])

    num_P2WPKH = sum([h_v["P2WPKH"] for h_v in p2sh.values()])
    num_P2WSH = sum([h_v["P2WSH"] for h_v in p2sh.values()])
    num_others = sum([h_v["others"] for h_v in p2sh.values()])

    t = num_multisig + num_nonstd + num_pubkey + num_pubkeyhash + num_scripthash + num_P2WPKH + num_P2WSH + num_others

    print("P2SH redeem scripts:")
    print("   Multisig: {}".format(num_multisig))
    print("   Nonstd: {}".format(num_nonstd))
    print("   P2PK: {}".format(num_pubkey))
    print("   P2PKH: {}".format(num_pubkeyhash))
    print("   P2SH: {}".format(num_scripthash))
    print("   P2WPKH: {}".format(num_P2WPKH))
    print("   P2WSH: {}".format(num_P2WSH))
    print("   Others: {}".format(num_others))
    print("Total: {}".format(t))


def p2sh_analysis(coin=BITCOIN):
    """
    Prints a summary of P2SH inputs data.

    :param coin: studied coin
    :return:
    """

    print("P2SH analysis")
    print("--------------------------")


    pickle_file = COIN_STR[coin] + "_p2sh"
    (p2sh, others_in_p2sh) = pickle.load(open(pickle_file + ".pickle", "rb"))

    # Number of redeem scripts per type
    p2sh_num_inputs_per_redeem_script_type(p2sh)

    avg_per_type, std_per_type, avg_abs, std_abs, avg_per_height = p2sh_average_size(p2sh)

    # Multisig scripts
    agg_data = p2sh_agg_height_dict(p2sh)
    pickle.dump((agg_data), open("p2sh_agg_data.pickle", "wb"))
    sorted_x = sorted(agg_data["multisig"].items(), key=operator.itemgetter(1))
    print(sorted_x)

    """
    [((11, 11), 1), ((8, 10), 1), ((0, 0), 1), ((13, 13), 1), ((3, 10), 1), ((1, 14), 1), ((6, 15), 1), ((4, 9), 1),
     ((4, 11), 1), ((5, 10), 1), ((6, 8), 1), ((1, 8), 1), ((6, 10), 2), ((1, 10), 2), ((0, 2), 2), ((2, 10), 2),
     ((7, 12), 2), ((2, 12), 3), ((8, 15), 3), ((1, 9), 3), ((2, 15), 3), ((3, 15), 5), ((5, 9), 5), ((12, 12), 5),
     ((8, 9), 5), ((15, 15), 5), ((6, 7), 8), ((12, 15), 8), ((10, 15), 9), ((9, 9), 17), ((5, 6), 20), ((5, 7), 24),
     ((1, 15), 26), ((3, 8), 26), ((6, 6), 39), ((2, 14), 66), ((2, 7), 72), ((7, 7), 90), ((6, 13), 100),
     ((5, 8), 116), ((1, 12), 117), ((10, 10), 131), ((8, 8), 150), ((5, 5), 200), ((2, 8), 224), ((3, 7), 410),
     ((4, 7), 749), ((1, 5), 1019), ((2, 9), 1022), ((1, 7), 1801), ((1, 4), 2187), ((4, 4), 2426), ((1, 6), 5864),
     ((4, 6), 7918), ((2, 5), 8826), ((4, 5), 10456), ((3, 3), 13357), ((3, 6), 17131), ((1, 3), 21334),
     ((1, 2), 86678), ((3, 5), 144958), ((2, 4), 209809), ((1, 1), 258449), ((3, 4), 453256), ((2, 6), 491146),
     ((2, 2), 22600200), ((2, 3), 56498831)]

    """

    # sorted(agg_data["nonstandard"].items(), key=operator.itemgetter(0))


def non_std_analysis(coin=BITCOIN):
    """
    Prints a summary of non-standard inputs data.

    :param coin: studied coin
    :return:
    """

    print("Non-std analysis")
    print("--------------------------")

    pickle_file = COIN_STR[coin] + "_non_std_inputs"
    (nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens) = pickle.load(open(pickle_file + ".pickle", "rb"))

    flatt_lens = flatten_dict_values(nonstd_sizes_lens)
    print("The average non-std input script len. is: {}".format(np.mean(flatt_lens)))
    print("There are {} empty scripts".format(sum([1 for e in flatt_lens if e == 0])))
    print("There are {} scripts of len 1".format(sum([1 for e in flatt_lens if e == 1])))
    print("There are {} different scripts".format(len(set(flatt_lens))))

    avg_per_height = {}
    for k, v in nonstd_sizes_lens.items():
        avg_per_height[k] = np.mean(v)
    diff_heights = sum([1 for v in avg_per_height.values() if not np.isnan(v)])
    print("Non-std scripts can be found in {} different blocks".format(diff_heights))

    # Are non-std scripts with len 0 misslabelled segwit inputs?
    flatt_outs = flatten_dict_values(nonstd_sizes_outs)
    print_first_x = 10
    ctr = 0
    for o, l in zip(flatt_outs, flatt_lens):
        if l == 0:
            print(o)
            ctr += 1
        if ctr == print_first_x:
            break
    # ... it does not seem so for bitcoin, but indeed they are for litecoin!


