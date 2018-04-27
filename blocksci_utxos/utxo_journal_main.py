import os
import blocksci

from constants import *
from get_blocksci_data import *
from analyze_data import *


if __name__ == "__main__":

    coin = BITCOIN # BITCOIN_CASH, LITECOIN
    chain = None

    if os.path.isdir("/home/ubuntu"):
        # AWS
        folders = {BITCOIN: "bitcoin", BITCOIN_CASH: "bitcoincash", LITECOIN: "litecoin"}
        chain = blocksci.Blockchain("/home/ubuntu/{}".format(folders[coin]))
    elif os.path.isdir("/home/bitcoin/BlockSci"):
        # deic-satoshi
        folders = {BITCOIN: "bitcoin", BITCOIN_CASH: "bitcoincash", LITECOIN: "litecoin"}
        chain = blocksci.Blockchain("/home/bitcoin/BlockSci/parsed-data-{}".format(folders[coin]))
    elif os.path.isdir("/mnt/bsafe/"):
        # blade
        folders = {BITCOIN: "", BITCOIN_CASH: "-bitcoincash", LITECOIN: "-litecoin"}
        chain = blocksci.Blockchain("/mnt/bsafe/blocksci-parsed-data".format(folders[coin]))

    # Get data and store it in pickle files
    print("Getting data from blocksci")
    blocksci_find_pk_in_p2pkh(chain, restart_from_height=None, coin=coin)
    blocksci_find_p2shinputs(chain, restart_from_height=None, coin=coin)
    blocksci_find_nonstd_inputs(chain, restart_from_height=None, coin=coin)
    blocksci_find_p2wsh_inputs(chain, restart_from_height=None, coin=coin)

    # RECSI paper
    blocksci_find_native_segwit_outputs(chain, restart_from_height=None, coin=coin)
    blocksci_find_native_segwit_inputs(chain, restart_from_height=None, coin=coin)

    # Read pickle files and create json files for STATUS
    print("Dumping estimations to json files")
    dump_estimations_to_json(coin=coin, input_type="ALL")

    # Additional analysis
    print("Maybe you're interested in kwnowing")
    non_std_analysis(coin=coin)
    p2sh_analysis(coin=BITCOIN)
