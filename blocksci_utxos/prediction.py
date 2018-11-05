#####################################################################
# Predicting if an output is going to be spent
#####################################################################

def sh_entropy(probs):
    return -sum(p * math.log(p, 2) for p in probs if p != 0)


def cond_sh_entropy(spent):
    spent_true = sum([v[True] for k, v in spent.items()])
    spent_false = sum([v[False] for k, v in spent.items()])
    total_outs = spent_true + spent_false

    s = 0
    for k, v in spent.items():
        px = (v[True] + v[False]) / total_outs
        cond_ent = sh_entropy([v[True] / (v[True] + v[False]), v[False] / (v[True] + v[False])])
        s += px * cond_ent

    return s


def quantizer(data, num_bins, q_type="linear"):
    mi = min(data.keys())
    ma = max(data.keys())
    intervals = np.linspace(mi, ma, num=num_bins + 1)
    agg_data = {i: {True: 0, False: 0} for i in range(len(intervals) - 1)}

    # We optimize for a sorted dictionary, although we can no enusre that it will be sorted, so
    # if we get to the end of the intervals, we start againat the beginning.
    # Not very nice, but it turns out it is much faster than iterating throguh intervals from the start each time
    i = 0
    for k, v in data.items():
        while not (
            (k > intervals[i] and k <= intervals[i + 1]) or (i == 0 and k >= intervals[0] and k <= intervals[1])):
            i = (i + 1) % len(intervals)

        agg_data[i][True] += v[True]
        agg_data[i][False] += v[False]

    assert sum([v[True] for k, v in data.items()]) == sum(
        [v[True] for k, v in agg_data.items()]), "Error: sum of Trues does not match"
    assert sum([v[False] for k, v in data.items()]) == sum(
        [v[False] for k, v in agg_data.items()]), "Error: sum of Falses does not match"

    return agg_data, intervals


spent_true = sum([v[True] for k, v in spent.items()])
spent_false = sum([v[False] for k, v in spent.items()])
total_outs = spent_true + spent_false

print(
    "There are {} outputs: {} spent ({}%) and {} unspent ({}%)".format(total_outs, spent_true, spent_true / total_outs,
                                                                       spent_false, spent_false / total_outs))
probs = [spent_true / total_outs, spent_false / total_outs]
sh_entropy(probs)

cond_sh_entropy(spent)

spent_height, spent_txsize, spent_scripttype, spent_amount, spent_iscoinbase = {}, {}, {}, {}, {}
for block in chain:
    for tx in block:
        for txout in tx.outs:
            if block.height not in spent_height.keys():
                spent_height[block.height] = {True: 0, False: 0}
            if tx.size_bytes not in spent_txsize.keys():
                spent_txsize[tx.size_bytes] = {True: 0, False: 0}
            if txout.address_type not in spent_scripttype.keys():
                spent_scripttype[txout.address_type] = {True: 0, False: 0}
            if txout.value not in spent_amount.keys():
                spent_amount[txout.value] = {True: 0, False: 0}
            if tx.is_coinbase not in spent_iscoinbase.keys():
                spent_iscoinbase[tx.is_coinbase] = {True: 0, False: 0}
            spent_height[block.height][txout.is_spent] += 1
            spent_txsize[tx.size_bytes][txout.is_spent] += 1
            spent_scripttype[txout.address_type][txout.is_spent] += 1
            spent_amount[txout.value][txout.is_spent] += 1
            spent_iscoinbase[tx.is_coinbase][txout.is_spent] += 1
    print(block.height)

pickle.dump((spent_height, spent_txsize, spent_scripttype, spent_amount, spent_iscoinbase),
            open("spent_condit.pickle", "wb"))

# He deixat llançat...
# ... però això no acaba mai
amount_100000, amount_100000_interv = quantizer(spent_amount, num_bins=100000, q_type="linear")
cond_sh_entropy(amount_100000)

# Get average fee-per-byte per block

fee_per_byte = [(block.height, np.mean(block.txes.fee_per_byte)) for block in chain]

#####################################################################
# When will an output be spent?
#####################################################################

# Will I be spent?
spent = {h:{True:0, False:0} for h in range(len(chain))}
for block in chain:
	for tx in block:
		for txout in tx.outs:
			if txout.is_spent:
				spent[block.height][True] += 1
			else:
				spent[block.height][False] += 1
	print(block.height)

pickle.dump((spent), open("spent_only.pickle", "wb"))


# When?
whens = {h:{} for h in range(len(chain))}
for block in chain:
	for tx in block:
		for txin in tx.ins:
			h = txin.spent_tx.block_height
			age = txin.age
			if age in whens[h].keys():
				whens[h][age] += 1
			else:
				whens[h][age] = 1
	print(block.height)

pickle.dump(whens, open("when_only.pickle", "wb"))


#####################################################################
# Predicting if an output is going to be spent
#####################################################################

grep 'out_type":0,' parsed_utxos_wp2sh.json | wc -l
grep 'out_type":1,' parsed_utxos_wp2sh.json | wc -l
grep 'out_type":2,' parsed_utxos_wp2sh.json | wc -l
grep 'out_type":3,' parsed_utxos_wp2sh.json | wc -l
grep 'out_type":4,' parsed_utxos_wp2sh.json | wc -l
grep 'out_type":5,' parsed_utxos_wp2sh.json | wc -l
grep '"non_std_type":"std' parsed_utxos_wp2sh.json | wc -l

grep '"non_std_type":"mul' parsed_utxos_wp2sh.json | wc -l
grep '"non_std_type":"P2WPKH' parsed_utxos_wp2sh.json | wc -l
grep '"non_std_type":"P2WSH' parsed_utxos_wp2sh.json | wc -l
grep '"non_std_type":fa' parsed_utxos_wp2sh.json | wc -l
cat parsed_utxos_wp2sh.json | wc -l
