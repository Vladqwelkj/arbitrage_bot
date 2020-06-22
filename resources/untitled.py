from binance_futures import binance_futures
b = binance_futures.Client(
    'vlRQQLtvtsSyNXxc6XD2xBSkaX1d3Ehn0gAlu3IJ5oBhZMRrmovaSiE6mSJy1zGa',
    'xp4X8h2XueQBJeJnhVtHrBOoTPRjWoqzPucWhB4lPN8My0VpqAIM8bkgzPtqGw6I',
    symbol='ETHUSDT',
    testnet=False,)

#print(b.position_info())

from bitmex import bitmex

b = bitmex(api_key='10OTgpO8u6tJYReF_9tpYXuT',
	api_secret='_I_1NPGhleO0EJwe2qfstyFz0NFleNgTwlNeuQV3Sa8t1lsv',
	test=False)

print((b.Position.Position_get().result()[0]))