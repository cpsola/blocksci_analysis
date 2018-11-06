import pickle

import blocksci
from external_apis import *

from constants import *


def blocksci_count_input_by_type(chain):
    """
    Counts how many inputs of each type are found in a given chain.

    Sample results:

    Bitcoin height 507952 (both v3 and v4):
        {address_type.nonstandard: 220758, address_type.pubkey: 1386719, address_type.pubkeyhash: 654245749,
        address_type.scripthash: 89171746, address_type.multisig: 166756, address_type.witness_pubkeyhash: 17750,
        address_type.witness_scripthash: 162311}

    Litecoin height 1364010 (both v3 and v4)
        {address_type.nonstandard: 4, address_type.pubkey: 315675, address_type.pubkeyhash: 53617822,
        address_type.scripthash: 1912089, address_type.multisig: 3, address_type.witness_pubkeyhash: 67,
        address_type.witness_scripthash: 2}


    :param chain: blocksci chain object
    :return: dictionary, keys are input types, values are number of occurrences
    """

    input_spending_type = {}
    for block in chain:
        for tx in block:
            for txin in tx.ins:
                if txin.address_type in input_spending_type.keys():
                    input_spending_type[txin.address_type] += 1
                else:
                    input_spending_type[txin.address_type] = 1

    return input_spending_type


def blocksci_utxo_set_size(chain):
    """
    Computes the number of utxos in a given chain. Computes current number of UTXOs at each block height.

    Note: it does not compute how many of the current UTXOs are found at a given height, but the number of UTXOs
    existing when we were at that height!

    :param chain: blocksci chain object
    :return: dictionary, key is block height, value is number of UTXOs
    """

    num_outputs, num_inputs = 0, 0
    utxo_set_size = []
    for block in chain:
        num_outputs += block.output_count
        num_inputs += block.input_count
        utxo_set_size.append((block.height, num_outputs - num_inputs))

    return utxo_set_size


def blocksci_find_pk_in_p2pkh(chain, restart_from_height=None, coin=BITCOIN):
    """
    Collects data about sizes of public keys revealed when spending P2PKH outputs. Two data sets are created,
    indexing the results by input height (the height where the public key is found) and output height (the
    height where the P2PKH script is found).

    Results are stored in two pickle files: COIN_pk_sizes_in and COIN_pk_sizes_out.

    Each pickle file contains two elements, a dictionary with public key sizes and an integer counting the
    number of unknowns found (should be 0).

    The public key sizes dictionary has block heights as keys and dictionaries as values. The values dictionaries
    contain the length of the public keys found in that block, and the number of times a public key with that length
    appears in the block, e.g.:
        {
            0: {},
            ...
            440000: {33: 2877, 65: 68},
            440001: {33: 4393, 65: 32}
        }

    Note: restart_from_height is not available in this function (checking the full blockchain is less than 1h).

    :param chain: blocksci chain object
    :param restart_from_height: height where the script starts running (data from previous blocks is loaded from
                                an existing pickle file).
    :param coin: studied coin
    :return:
    """

    # Storing block height of the INPUT
    pickle_file = COIN_STR[coin] + "_pk_sizes_in"
    pubkey_sizes = {}
    unknowns = 0
    for block in chain:
        this_block = {}
        for tx in block:
            for txin in tx.ins:
                if txin.address_type == blocksci.address_type.pubkeyhash:
                    # if txin.address.script.pubkey:  # v0.4
                    if txin.address.pubkey:
                        # l = len(txin.address.script.pubkey)  # v0.4
                        l = len(txin.address.pubkey)
                        if l in this_block.keys():
                            this_block[l] += 1
                        else:
                            this_block[l] = 1
                    else:
                        unknowns += 1
        pubkey_sizes[block.height] = this_block
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
                    # if txin.address.script.pubkey:  # v0.4
                    if txin.address.pubkey:
                        # l = len(txin.address.script.pubkey)  # v0.4
                        l = len(txin.address.pubkey)
                        h = txin.spent_tx.block_height
                        pubkey_sizes_outs[h][l] += 1
                    else:
                        unknowns_outs += 1
        print(block.height)

    pickle.dump((pubkey_sizes_outs, unknowns_outs), open(pickle_file + ".pickle", "wb"))


def blocksci_find_p2sh_inputs(chain, restart_from_height=None, coin=BITCOIN):
    """
    Function to find all spent P2SH scripts and to store data about its type, by input height. Data is stored in a
    pickle file.

    p2sh is a dictionary with keys the block height and values another dictionary d1.
        d1 is a dictionary with keys the script type and values either a dictionary or an integer, depending on the
        type (see p2sh_sizes variable initialization).
        - for types "multisig", "nonstandard", "pubkey" and "pubkeyhash", value is a dictionary d2.
            d2 is a dictionary with keys the subtypes or lengths of some variable, and value the number of scripts of
            that type.
        - for types "scripthash", "P2WPKH", "P2WSH" and "others", value is an integer.
            the integer denotes the number of scripts of that type.

    For instance, p2sh[500000] is
        {'P2WPKH': 94, 'pubkeyhash': {}, 'multisig': {(1, 2): 4, (2, 3): 658, (2, 4): 40, (2, 2): 54},
            'scripthash': {}, 'others': 0, 'P2WSH': 224, 'pubkey': {}, 'nonstandard': {}}

    Progress is saved each SAVE_HEIGHT_INTERVAL blocks and can be recovered using the restart_from_height parameter.

    :param chain: blocksci chain object
    :param restart_from_height: height where the script starts running (data from previous blocks is loaded from
                                an existing pickle file).
    :param coin: studied coin
    :return:
    """

    pickle_file = COIN_STR[coin] + "_p2sh"

    if restart_from_height:
        (p2sh, others_in_p2sh) = pickle.load(open(pickle_file+str(restart_from_height)+".pickle", "rb"))
    else:
        p2sh = {}
        others_in_p2sh = []
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
                        # if txin.address.script.wrapped_address.type == blocksci.address_type.multisig: # v0.4
                        if txin.address.wrapped_address.type == blocksci.address_type.multisig:
                            # n = txin.address.script.wrapped_script.required # v0.4
                            # m = txin.address.script.wrapped_script.total # v0.4
                            n = txin.address.wrapped_address.required
                            m = txin.address.wrapped_address.total
                            if (n, m) in p2sh_sizes["multisig"].keys():
                                p2sh_sizes["multisig"][(n, m)] += 1
                            else:
                                p2sh_sizes["multisig"][(n, m)] = 1

                        elif txin.address.wrapped_address.type == blocksci.address_type.nonstandard:
                            lens, _ = get_script_size_API([(tx.hash, i)], coin)
                            l = lens[0]
                            if l in p2sh_sizes["nonstandard"].keys():
                                p2sh_sizes["nonstandard"][l] += 1
                            else:
                                p2sh_sizes["nonstandard"][l] = 1

                        elif txin.address.wrapped_address.type == blocksci.address_type.pubkey:
                            l = len(txin.address.wrapped_address.pubkey)
                            if l in p2sh_sizes["pubkey"].keys():
                                p2sh_sizes["pubkey"][l] += 1
                            else:
                                p2sh_sizes["pubkey"][l] = 1

                        elif txin.address.wrapped_address.type == blocksci.address_type.pubkeyhash:
                            l = len(txin.address.wrapped_address.pubkey)
                            if l in p2sh_sizes["pubkeyhash"].keys():
                                p2sh_sizes["pubkeyhash"][l] += 1
                            else:
                                p2sh_sizes["pubkeyhash"][l] = 1

                        elif txin.address.wrapped_address.type == blocksci.address_type.scripthash:
                            lens, _ = get_script_size_API([(tx.hash, i)], coin)
                            l = lens[0]
                            if l in p2sh_sizes["scripthash"].keys():
                                p2sh_sizes["scripthash"][l] += 1
                            else:
                                p2sh_sizes["scripthash"][l] = 1

                        elif txin.address.wrapped_address.type == blocksci.address_type.witness_pubkeyhash:
                            p2sh_sizes["P2WPKH"] += 1

                        elif txin.address.wrapped_address.type == blocksci.address_type.witness_scripthash:
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
    """
    Collects data about sizes of non standard inputs, indexed by input height.

    Results are stored in a pickle file: COIN_non_std_inputs.

    The pickle file contains three dictionaries, each one indexed by input block height:
        nonstd_sizes_outs: stores input identifiers (transaction hash and input index) # TODO: why is it called outs?
        nonstd_sizes_scripts: stores scripts
        nonstd_sizes_lens: stores script sizes

    For instance, for height 129878:

    nonstd_sizes_outs[129878]:
        [('8ebe1df6ebf008f7ec42ccd022478c9afaec3ca0444322243b745aa2e317c272', 0)]
    nonstd_sizes_scripts[129878]:
        ['49304602210095e9fe42a22dfc8e8f950bc900f34126cc9d24f666fbd587a7b062d09830983e022100b7588f0f6152a12e1d3fa449bd
        87e6d28a143f96b4d6bfd6b03e18a24e7f61cd01']
    nonstd_sizes_lens[129878]
        [74.0]

    Progress is saved each SAVE_HEIGHT_INTERVAL blocks and can be recovered using the restart_from_height parameter.

    :param chain: blocksci chain object
    :param restart_from_height: height where the script starts running (data from previous blocks is loaded from
                                an existing pickle file).
    :param coin: studied coin
    :return:
    """

    pickle_file = COIN_STR[coin] + "_non_std_inputs"

    if restart_from_height:
        (nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (outs), scripts (scripts) and script lengths (lens)
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
                        nonstd_sizes_outs[h].append((str(tx.hash), i))
                        nonstd_sizes_scripts[h].append(scripts[0])
                        nonstd_sizes_lens[h].append(lens[0])

                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens), open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((nonstd_sizes_outs, nonstd_sizes_scripts, nonstd_sizes_lens), open(pickle_file + ".pickle", "wb"))


def blocksci_find_p2wsh_inputs(chain, restart_from_height=None, coin=BITCOIN):
    """

    Collects data about sizes of P2WSH witness scripts, indexed by input height.

    Results are stored in a pickle file: COIN_p2wsh_inputs.

    The pickle file contains three dictionaries, each one indexed by input block height:
        p2wsh_sizes_outs: stores input identifiers (transaction hash and input index) # TODO: why is it called outs?
        p2wsh_sizes_scripts: stores scripts
        p2wsh_sizes_lens: stores script sizes

    For instance, for height 482133:
        p2wsh_sizes_outs[482133]:
            [('cab75da6d7fe1531c881d4efdb4826410a2604aa9e6442ab12a08363f34fb408', 0)]

        p2wsh_sizes_scripts[482133]
            ['0300483045022100a9a7b273afe54da5f087cb2d995180251f2950cb3b08cd7126f3ebe0d9323335022008c49c695f8951fbb6
            837e157b9a243dc8a6c79334af529cde6af20a1749efef0125512103534da516a0ab32f30246620fdfbfaf1921228c1e222c6bd2
            fcddbcfd9024a1b651ae']

        p2wsh_sizes_lens[482133]
            [113.0]


    Progress is saved each SAVE_HEIGHT_INTERVAL blocks and can be recovered using the restart_from_height parameter.

    :param chain: blocksci chain object
    :param restart_from_height: height where the script starts running (data from previous blocks is loaded from
                                an existing pickle file).
    :param coin: studied coin
    :return:
    """

    pickle_file = COIN_STR[coin] + "_p2wsh_inputs"

    if restart_from_height:
        (p2wsh_sizes_outs, p2wsh_sizes_scripts, p2wsh_sizes_lens) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (outs), witness scripts (scripts) and witness script lengths (lens)
        p2wsh_sizes_outs = {h: [] for h in range(len(chain))}
        p2wsh_sizes_scripts = {h: [] for h in range(len(chain))}
        p2wsh_sizes_lens = {h: [] for h in range(len(chain))}
        restart_from_height = -1

    # First P2WSH input is in block 482133
    # for block in chain[482133:]:
    for block in chain:
        if block.height > restart_from_height:
            print(block.height)
            for tx in block:
                i = 0
                for txin in tx.ins:
                    if txin.address_type == blocksci.address_type.witness_scripthash:
                        lens, scripts = get_witness_size_API([(tx.hash, i)], coin)
                        h = block.height
                        p2wsh_sizes_outs[h].append((str(tx.hash), i))
                        p2wsh_sizes_scripts[h].append(scripts[0])
                        p2wsh_sizes_lens[h].append(lens[0])

                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((p2wsh_sizes_outs, p2wsh_sizes_scripts, p2wsh_sizes_lens), open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((p2wsh_sizes_outs, p2wsh_sizes_scripts, p2wsh_sizes_lens), open(pickle_file + ".pickle", "wb"))


def blocksci_find_native_segwit_outputs(chain, restart_from_height=None, coin=BITCOIN):
    """
    Collects data about native segwit scripts (P2WSH and P2WPKH), indexed by output height.

    Results are stored in a pickle file: COIN_nativesegwit_outputs.

    The pickle file contains four dictionaries, each one indexed by output block height:

        p2wsh_outs: identifiers of native P2WSH outputs (transaction id and output index)
        p2wsh_outs_spent: dictionary with number of spent and unspent outputs

        p2wpkh_outs: identifiers of native P2WPK outputs (transaction id and output index)
        p2wpkh_outs_spent: dictionary with number of spent and unspent outputs

    For instance, for height 482133:
        p2wpkh_outs[482133]: [(cab75da6d7fe1531c881d4efdb4826410a2604aa9e6442ab12a08363f34fb408, 0)]
        p2wpkh_outs_spent[482133]: {True: 1, False: 0}

        p2wsh_outs[482133]: [(bd430d52f35166a7dd6251c73a48559ad8b5f41b6c5bc4a6c4c1a3e3702f4287, 0)]
        p2wsh_outs_spent[482133]: {True: 1, False: 0}


    Progress is saved each SAVE_HEIGHT_INTERVAL blocks and can be recovered using the restart_from_height parameter.

    :param chain: blocksci chain object
    :param restart_from_height: height where the script starts running (data from previous blocks is loaded from
                                an existing pickle file).
    :param coin: studied coin
    :return:
    """

    pickle_file = COIN_STR[coin] + "_nativesegwit_outputs"

    if restart_from_height:
        (p2wsh_outs, p2wsh_outs_spent, p2wpkh_outs, p2wpkh_outs_spent) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (outs) and how many outputs have been spent (spent)
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
                        p2wsh_outs_spent[h][txout.is_spent] += 1
                    if txout.address_type == blocksci.address_type.witness_pubkeyhash:
                        h = block.height
                        p2wpkh_outs[h].append((tx.hash, i))
                        p2wpkh_outs_spent[h][txout.is_spent] += 1
                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((p2wsh_outs, p2wsh_outs_spent, p2wpkh_outs, p2wpkh_outs_spent),
                            open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((p2wsh_outs, p2wsh_outs_spent, p2wpkh_outs, p2wpkh_outs_spent), open(pickle_file + ".pickle", "wb"))


def blocksci_find_native_segwit_inputs(chain, restart_from_height=None, coin=BITCOIN):
    """
    Collects data about native segwit scripts (P2WSH and P2WPKH), indexed by input height.

    Results are stored in a pickle file: COIN_nativesegwit_inputs.

    The pickle file contains two dictionaries, each one indexed by input block height:

        p2wsh_ins: identifiers of native P2WSH inputs (transaction id and input index)
        p2wpkh_ins: identifiers of native P2WPK inputs (transaction id and input index)

    For instance, for height 481824:
        p2wpkh_ins[481824]: [('f91d0a8a78462bc59398f2c5d7a84fcff491c26ba54c4833478b202796c8aafd', 0)]

    Progress is saved each SAVE_HEIGHT_INTERVAL blocks and can be recovered using the restart_from_height parameter.

    :param chain: blocksci chain object
    :param restart_from_height: height where the script starts running (data from previous blocks is loaded from
                                an existing pickle file).
    :param coin: studied coin
    :return:
    """

    pickle_file = COIN_STR[coin] + "_nativesegwit_inputs"

    if restart_from_height:
        (p2wsh_ins, p2wpkh_ins) = pickle.load(
            open(pickle_file + str(restart_from_height) + ".pickle", "rb"))
    else:
        # Store txhash and input index (ins)
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
                        p2wsh_ins[h].append((str(tx.hash), i))
                    if txin.address_type == blocksci.address_type.witness_pubkeyhash:
                        h = block.height
                        p2wpkh_ins[h].append((str(tx.hash), i))
                    i += 1

            if block.height % SAVE_HEIGHT_INTERVAL == 0:
                pickle.dump((p2wsh_ins, p2wpkh_ins),
                            open(pickle_file + str(block.height) + ".pickle", "wb"))

    pickle.dump((p2wsh_ins, p2wpkh_ins), open(pickle_file + ".pickle", "wb"))


