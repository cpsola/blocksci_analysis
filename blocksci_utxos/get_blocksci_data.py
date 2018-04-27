import pickle

import blocksci
from external_apis import *

from constants import *


def blocksci_count_input_by_type(chain, restart_from_height=None, coin=BITCOIN):

    """
    Exploratory analysis: Input types
    :param chain:
    :param restart_from_height:
    :param coin:
    :return:
    """

    input_spending_type = {}
    for block in chain:
        for tx in block:
            for txin in tx.ins:
                if txin.address_type in input_spending_type.keys():
                    input_spending_type[txin.address_type] += 1
                else:
                    input_spending_type[txin.address_type] = 1

    # input_spending_type:
    # Bitcoin height 507952 (both v3 and v4):
    # {address_type.nonstandard: 220758, address_type.pubkey: 1386719, address_type.pubkeyhash: 654245749, address_type.scripthash: 89171746, address_type.multisig: 166756, address_type.witness_pubkeyhash: 17750, address_type.witness_scripthash: 162311}
    # Litecoin height 1364010 (both v3 and v4)
    # {address_type.nonstandard: 4, address_type.pubkey: 315675, address_type.pubkeyhash: 53617822, address_type.scripthash: 1912089, address_type.multisig: 3, address_type.witness_pubkeyhash: 67, address_type.witness_scripthash: 2}
    return input_spending_type


def blocksci_utxo_set_size(chain):
    #####################################################################
    # Size of the UTXO set
    #####################################################################

    num_outputs = 0
    num_inputs = 0
    utxo_set_size = []
    for block in chain:
        num_outputs += block.output_count
        num_inputs += block.input_count
        utxo_set_size.append((block.height, num_outputs - num_inputs))

    return utxo_set_size


def blocksci_find_pk_in_p2pkh(chain, restart_from_height=None, coin=BITCOIN):

    #####################################################################
    # From all inputs spending P2PKH outputs, how are PKs used? Compressed? Uncompressed?
    #####################################################################

    # Storing block height of the INPUT
    pickle_file = COIN_STR[coin] + "_pk_sizes_in"
    pubkey_sizes = {}
    unknowns = 0
    for block in chain:
        thisblock = {}
        for tx in block:
            for txin in tx.ins:
                if txin.address_type == blocksci.address_type.pubkeyhash:
                    if txin.address.script.pubkey:
                        l = len(txin.address.script.pubkey)
                        if l in thisblock.keys():
                            thisblock[l] += 1
                        else:
                            thisblock[l] = 1
                    else:
                        unknowns += 1
        pubkey_sizes[block.height] = thisblock
        print(block.height)

    pickle.dump((pubkey_sizes, unknowns), open(pickle_file+ ".pickle", "wb"))


    # Storing block height of the OUTPUT
    pickle_file = COIN_STR[coin] + "_pk_sizes_out"
    pubkey_sizes_outs = {h: {33: 0, 65: 0} for h in range(len(chain))}
    unknowns_outs = 0
    for block in chain:
        for tx in block:
            for txin in tx.ins:
                if txin.address_type == blocksci.address_type.pubkeyhash:
                    if txin.address.script.pubkey:
                        l = len(txin.address.script.pubkey)
                        h = txin.spent_tx.block_height
                        pubkey_sizes_outs[h][l] += 1
                    else:
                        unknowns_outs += 1
        print(block.height)

    pickle.dump((pubkey_sizes_outs, unknowns_outs), open(pickle_file + ".pickle", "wb"))


def blocksci_find_p2shinputs(chain, restart_from_height=None, coin=BITCOIN):
    """
    Function to find all spent P2SH scripts and to store data about its type, by height. Data is stored in a pickle
     file.

    p2sh is a dictionary with keys the block height and values another dictionary d1.
        d1 is a dictionary with keys the script type and values either a dictionary of an integer, depending on the
        type (see p2sh_sizes variable initialization).
        - for types "multisig", "nonstandard", "pubkey" and "pubkeyhash", value is a dictionary d2.
            d2 is a dictionary with keys the subtypes or lengths of some variable, and value the number of scripts of
            that type.
        - for types "scripthash", "P2WPKH", "P2WSH" and "others", value is an integer.
            the integer denotes the number of scripts of that type.

    For instance, p2sh[500000] is
        {'P2WPKH': 94, 'pubkeyhash': {}, 'multisig': {(1, 2): 4, (2, 3): 658, (2, 4): 40, (2, 2): 54},
            'scripthash': {}, 'others': 0, 'P2WSH': 224, 'pubkey': {}, 'nonstandard': {}}

    :return:
    """

    pickle_file = COIN_STR[coin] + "_p2sh"

    if restart_from_height:
        (p2sh, others_in_p2sh) = pickle.load(open(pickle_file+str(restart_from_height)+".pickle", "rb"))
    else:
        p2sh = {}
        others_in_p2sh = []
        #p2sh_in_p2sh = []
        #nonstd_in_p2sh = []
        restart_from_height = -1

    for block in chain:
        if block.height > restart_from_height:
            print(block.height)
            p2sh_sizes = {"multisig": {}, 'nonstandard': {}, 'pubkey': {}, "pubkeyhash": {}, "scripthash": {},
                          "P2WPKH": 0, "P2WSH": 0, "others": 0}
            for tx in block:
                i = 0
                for txin in tx.ins:
                    if txin.address_type == blocksci.address_type.scripthash:
                        if txin.address.script.wrapped_address.type == blocksci.address_type.multisig:
                            n = txin.address.script.wrapped_script.required
                            m = txin.address.script.wrapped_script.total
                            if (n, m) in p2sh_sizes["multisig"].keys():
                                p2sh_sizes["multisig"][(n, m)] += 1
                            else:
                                p2sh_sizes["multisig"][(n, m)] = 1

                        elif txin.address.script.wrapped_address.type == blocksci.address_type.nonstandard:
                            # nonstd_in_p2sh.append((tx.hash, i))
                            lens, _ = get_script_size_API([(tx.hash, i)], coin)
                            l = lens[0]
                            if l in p2sh_sizes["nonstandard"].keys():
                                p2sh_sizes["nonstandard"][l] += 1
                            else:
                                p2sh_sizes["nonstandard"][l] = 1

                        elif txin.address.script.wrapped_address.type == blocksci.address_type.pubkey:
                            l = len(txin.address.script.wrapped_script.pubkey)
                            if l in p2sh_sizes["pubkey"].keys():
                                p2sh_sizes["pubkey"][l] += 1
                            else:
                                p2sh_sizes["pubkey"][l] = 1

                        elif txin.address.script.wrapped_address.type == blocksci.address_type.pubkeyhash:
                            l = len(txin.address.script.wrapped_script.pubkey)
                            if l in p2sh_sizes["pubkeyhash"].keys():
                                p2sh_sizes["pubkeyhash"][l] += 1
                            else:
                                p2sh_sizes["pubkeyhash"][l] = 1

                        elif txin.address.script.wrapped_address.type == blocksci.address_type.scripthash:
                            # p2sh_in_p2sh.append((tx.hash, i))
                            lens, _ = get_script_size_API([(tx.hash, i)], coin)
                            l = lens[0]
                            if l in p2sh_sizes["scripthash"].keys():
                                p2sh_sizes["scripthash"][l] += 1
                            else:
                                p2sh_sizes["scripthash"][l] = 1

                        elif txin.address.script.wrapped_address.type == blocksci.address_type.witness_pubkeyhash:
                            p2sh_sizes["P2WPKH"] += 1

                        elif txin.address.script.wrapped_address.type == blocksci.address_type.witness_scripthash:
                            p2sh_sizes["P2WSH"] += 1

                        else:
                            p2sh_sizes["others"] += 1
                            others_in_p2sh.append((tx.hash, i))
                    i += 1

            p2sh[block.height] = p2sh_sizes

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((p2sh, others_in_p2sh), open(pickle_file+str(block.height)+".pickle", "wb"))

    pickle.dump((p2sh, others_in_p2sh), open(pickle_file+".pickle", "wb"))


def blocksci_find_nonstd_inputs(chain, restart_from_height=None, coin=BITCOIN):

    #####################################################################
    # Non-std
    #####################################################################

    pickle_file = COIN_STR[coin] + "_non_std_inputs"

    if restart_from_height:
        (nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (outs), scripts (scripts) and
        # script lengths (lens)
        nonstd_sizes_outs = {h: [] for h in range(len(chain))}
        nonstd_sizes_scripts = {h: [] for h in range(len(chain))}
        nonstd_sizes_lens = {h: [] for h in range(len(chain))}
        restart_from_height = -1

    for block in chain:
        if block.height > restart_from_height:
            print(block.height)
            for tx in block:
                i = 0
                for txin in tx.ins:
                    if txin.address_type == blocksci.address_type.nonstandard:
                        lens, scripts = get_script_size_API([(tx.hash, i)], coin)
                        h = block.height
                        nonstd_sizes_outs[h].append((tx.hash, i))
                        nonstd_sizes_scripts[h].append(scripts[0])
                        nonstd_sizes_lens[h].append(lens[0])

                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens), open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens), open(pickle_file + ".pickle", "wb"))


def blocksci_find_p2wsh_inputs(chain, restart_from_height=None, coin=BITCOIN):

    #####################################################################
    # P2WSH
    #####################################################################

    pickle_file = COIN_STR[coin] + "_p2wsh_inputs"

    if restart_from_height:
        (p2wsh_sizes_outs, p2wsh_sizes_scripts, p2wsh_sizes_lens) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (outs), witness scripts (scripts) and
        # witness script lengths (lens)
        p2wsh_sizes_outs = {h: [] for h in range(len(chain))}
        p2wsh_sizes_scripts = {h: [] for h in range(len(chain))}
        p2wsh_sizes_lens = {h: [] for h in range(len(chain))}
        restart_from_height = -1

    # First P2WSH input is in block 482133
    #for block in chain[482133:]:
    for block in chain:
        if block.height > restart_from_height:
            print(block.height)
            for tx in block:
                i = 0
                for txin in tx.ins:
                    if txin.address_type == blocksci.address_type.witness_scripthash:
                        lens, scripts = get_witness_size_API([(tx.hash, i)], coin)
                        h = block.height
                        p2wsh_sizes_outs[h].append((tx.hash, i))
                        p2wsh_sizes_scripts[h].append(scripts[0])
                        p2wsh_sizes_lens[h].append(lens[0])

                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((p2wsh_sizes_outs, p2wsh_sizes_scripts, p2wsh_sizes_lens), open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((p2wsh_sizes_outs, p2wsh_sizes_scripts, p2wsh_sizes_lens), open(pickle_file + ".pickle", "wb"))


def blocksci_find_native_segwit_outputs(chain, restart_from_height=None, coin=BITCOIN):

    #####################################################################
    # P2WSH AND P2WPKH
    #####################################################################

    pickle_file = COIN_STR[coin] + "_nativesegwit_outputs"

    if restart_from_height:
        (p2wsh_outs, p2wsh_outs_spent, p2wpkh_outs, p2wpkh_outs_spent) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (outs), witness scripts (scripts) and
        # witness script lengths (lens)
        p2wsh_outs = {h: [] for h in range(len(chain))}
        p2wsh_outs_spent = {h: {True: 0, False: 0} for h in range(len(chain))}

        p2wpkh_outs = {h: [] for h in range(len(chain))}
        p2wpkh_outs_spent = {h: {True: 0, False: 0} for h in range(len(chain))}

        restart_from_height = -1

    # First P2WSH input is in block 482133
    #for block in chain[482133:]:
    for block in chain:
        if block.height > restart_from_height:
            print(block.height)
            for tx in block:
                i = 0
                for txout in tx.outs:
                    if txout.address_type == blocksci.address_type.witness_scripthash:
                        h = block.height
                        p2wsh_outs[h].append((tx.hash, i))
                        p2wsh_outs_spent[txout.is_spent] += 1
                    if txout.address_type == blocksci.address_type.witness_pubkeyhash:
                        h = block.height
                        p2wpkh_outs[h].append((tx.hash, i))
                        p2wpkh_outs_spent[txout.is_spent] += 1
                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((p2wsh_outs, p2wsh_outs_spent, p2wpkh_outs, p2wpkh_outs_spent),
                            open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((p2wsh_outs, p2wsh_outs_spent, p2wpkh_outs, p2wpkh_outs_spent), open(pickle_file + ".pickle", "wb"))


def blocksci_find_native_segwit_inputs(chain, restart_from_height=None, coin=BITCOIN):

    #####################################################################
    # P2WSH AND P2WPKH
    #####################################################################

    pickle_file = COIN_STR[coin] + "_nativesegwit_inputs"

    if restart_from_height:
        (p2wsh_ins, p2wpkh_ins) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (outs), witness scripts (scripts) and
        # witness script lengths (lens)
        p2wsh_ins = {h: [] for h in range(len(chain))}
        p2wpkh_ins = {h: [] for h in range(len(chain))}
        restart_from_height = -1

    # SegWit was activated in block 481824
    for block in chain[481824:]:
    #for block in chain:
        if block.height > restart_from_height:
            print(block.height)
            for tx in block:
                i = 0
                for txin in tx.ins:
                    if txin.address_type == blocksci.address_type.witness_scripthash:
                        h = block.height
                        p2wsh_ins[h].append((tx.hash, i))
                    if txin.address_type == blocksci.address_type.witness_pubkeyhash:
                        h = block.height
                        p2wpkh_ins[h].append((tx.hash, i))
                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((p2wsh_ins, p2wpkh_ins),
                            open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((p2wsh_ins, p2wpkh_ins), open(pickle_file + ".pickle", "wb"))


