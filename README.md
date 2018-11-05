# BlockSci UTXOs

Python3/jupyter code for extracting data from blocksci and creating estimation JSON files to feed STATUS.

### Running:

Execute:

```python3 utxo_journal_main.py```

By default, the code analyses the Bitcoin blockchain.
Change the value of the variable `coin` in `utxo_journal_main.py` to analyze other coins
(allowed values are `BITCOIN`, `BITCOIN_CASH`, and `LITECOIN`).

### Structure:

The main folder contains `python3` code to extract data from `blocksci`. Specifically, it obtains data about the sizes of:
* Compressed/uncompressed public keys in P2PKH inputs.
* Input scripts of P2SH inputs.
* Input scripts of non-standard inputs.
* Witness scripts of native P2WSH inputs.

The `notebooks` folder contains jupyter notebooks for creating plots to visualize the extracted data. Notebooks
can be used **after** having executed `utxo_journal_main.py`, since notebooks only plot the data (that has to be first
collected with the `utxo_journal_main.py` script).

### Dependencies

Install `blocksci` and libraries in `requirements.txt`.



