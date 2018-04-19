from time import sleep

import requests

from constants import *

cache_response, cache_txid = None, None

def get_script_size_API(list_of_inputs, coin):
    """
    Queries blockchain.info API for script length of P2SH redeem scripts (P2SH nested in P2SH).

    :param p2sh_in_p2sh:
    :return: tuple, list with script lengths and list with scripts
    """

    def get_script(txid, input_ind, coin):

        global cache_response, cache_txid

        def get_url(txid, input_ind, coin):
            if coin == BITCOIN:
                return "https://blockchain.info/rawtx/{}".format(txid)
            elif coin == LITECOIN:
                return "https://insight.litecore.io/api/tx/{}".format(txid)
            elif coin == BITCOIN_CASH:
                return "https://bitcoincash.blockexplorer.com/api/tx/{}".format(txid)
            else:
                raise Exception

        def get_hex_script_from_json(response, txid, input_ind):
            if coin == BITCOIN:
                return response["inputs"][input_ind]["script"]
            elif coin == LITECOIN:
                assert response["vin"][input_ind]["n"] == input_ind
                return response["vin"][input_ind]["scriptSig"]["hex"]
            elif coin == BITCOIN_CASH:
                assert response["vin"][input_ind]["n"] == input_ind
                return response["vin"][input_ind]["scriptSig"]["hex"]
            else:
                raise Exception

        if str(cache_txid) == str(txid):
            response = cache_response
        else:
            url = get_url(txid, input_ind, coin)
            req = requests.request('GET', url)
            response = req.json()
            cache_response, cache_txid = response, txid
            sleep(5)

        script = get_hex_script_from_json(response, txid, input_ind)
        return script

    sizes = []
    scripts = []

    for inp in list_of_inputs:
        (txid, input_ind) = inp
        try:
            script = get_script(txid, input_ind, coin)
        except:
            print("sleeping for an hour...")
            sleep(3600)
            script = get_script(txid, input_ind, coin)
        scripts.append(script)
        sizes.append(len(script)/2)

    return sizes, scripts


def get_witness_size_API(list_of_inputs, coin):
    """
    Queries blockchain.info API for witness script lenghts.

    :param list_of_inputs: list of tuples (transaction id, input index)
    :return: tuple, list with script lengths and list with scripts
    """

    def get_script(txid, input_ind, coin):

        if coin == BITCOIN:
            url = "https://blockchain.info/rawtx/"
            req = requests.request('GET', url + str(txid))
            response = req.json()
            script = response["inputs"][input_ind]["witness"]
            sleep(0.25)
        elif coin == LITECOIN:
            # These APIs do not seem to include witness scripts
            # url = "https://chain.so/api/v2/get_tx_inputs/LTC/"
            # url = "https://api.blockcypher.com/v1/ltc/main/txs/{}/?instart={}&limit=1".format(txid, input_ind)
            # url = "https://insight.litecore.io/api/tx/{}".format(txid)

            url = "https://chainz.cryptoid.info/explorer/tx.raw.dws?coin=ltc&id={}&fmt.js".format(txid)
            req = requests.request('GET', url)
            response = req.json()
            data_pushes_script = response["vin"][input_ind]["txinwitness"]
            # This API returns a list with data pushes in the witness, so we need to reconstruct the script:
            script = "".join(["{:02x}{}".format(int(len(d)/2), d) for d in data_pushes_script if d != ""])
            sleep(1)
        else:
            raise Exception

        return script

    sizes = []
    scripts = []

    for inp in list_of_inputs:
        (txid, input_ind) = inp
        script = get_script(txid, input_ind, coin)
        scripts.append(script)
        sizes.append(len(script)/2)

    return sizes, scripts