# from audioop import add
from concurrent.futures import ProcessPoolExecutor, as_completed
import subprocess
import os
from tqdm import tqdm, trange
max_workers = os.cpu_count() - 2
valids = []
def ping(ip):
    # pbar.update(1)
    res = subprocess.call(['ping', '-n',str(1),'-w',str(10), ip], stdout=subprocess.DEVNULL)
    return res, ip 
if __name__ == "__main__":

    with ProcessPoolExecutor(max_workers=max_workers) as executor:

        futures = [
            executor.submit(
                ping, f"192.168.{x}.{y}" 
            ) for x in range(1,255) for y in range(1,255)
        ]
        for _ in tqdm(
                    as_completed(futures),
                    total=len(255*255),
                    desc=f"Searching",
                ):
                    pass
        executor.shutdown(wait=True)
        results = [f.result()[0] for f in futures]
        ips = [f.result()[1] for f in futures]
        for idr, res in results:
            if res==0:
                print(f"{ips[idr]} online!")
# for pingp in range(1,255):
#     for ping in range(1,255):
#         address = "192.168." + str(pingp) + "." + str(ping)
#         if res == 0:
#             print ("ping to", address, "OK")
#             valids.append(address)
#         elif res == 2:
#             print ("no response from", address)
#         else:
#             print ("ping to", address, "failed!")

# import multiprocessing
# import subprocess
# num_threads = int(0.8*multiprocessing.cpu_count())
# valids = []
# def ping(ip):
#     success = subprocess.call(['ping', '-n',str(1),'-w',str(10), ip], stdout = subprocess.DEVNULL)
#     if success == 0:
#         print("{} responded".format(ip))
#         valids.append(ip)
#     else:
#         print("{} not pingable".format(ip))
#     return True if success == 0 else False

# def ping_range(start, end):
#     with multiprocessing.Pool(num_threads) as pool:
#         pool.map(ping, [f"192.168.{x}.{y}" for x in range(start, end) for y in range(start, end)])

# ping_range(1,2)
# print(valids)