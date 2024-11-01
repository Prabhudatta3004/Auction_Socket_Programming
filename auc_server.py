''' NAMES: KABIR SINGH BHATIA(kbhatia), PRABHUDATTA MISHRA (pmishra4)
    DATE: 16th October, 2024'''
import socket
import threading
import argparse

class AuctioneerServer:
    def __init__(self, host, port):
        self.host = host    # Server IP address
        self.port = port    # Server port number
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create TCP socket
        self.status = 0     # 0: Waiting for seller, 1: Waiting for buyer 
        self.seller_conn = None     # Connection object for seller
        self.buyers = []    # List to store connected buyers (conn, buyer_id)
        self.bids = {}      # Dictionary to store bids by buyer id  
        self.ongoing = False    # Flag that indicates whether the bidding is on-going
        self.auction_details = None     # Store auction details
        self.buyer_lock = threading.RLock()     # Reentrant lock for synchronizing access to buyers

    def start_server(self):
        # Bind server socket and start listening for connections
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Auctioneer is ready for hosting auctions!")

        while True:
            conn, addr = self.server_socket.accept()
            if self.ongoing:
                conn.send(b"Auction is ongoing. Please try again later\n")
                conn.close()
            if self.status == 0:    # Waiting for seller
                print(f"New Seller is connected from {addr[0]}:{addr[1]}")
                threading.Thread(target=self.handle_seller, args=(conn, addr)).start()      # Handling seller in a new thread
            elif self.status == 1:  # Waiting for buyers
                if not self.auction_details:    # If buyer connects when seller has not submitted auction request yet
                    conn.sendall(b"Seller is busy. Try to connect again later\n")
                    conn.close()
                else:
                    threading.Thread(target=self.handle_buyer, args=(conn, addr)).start()   # Handle buyer in a new thread       

    def handle_seller(self, conn, addr):
        print(">> New Seller Thread spawned")   # Server log
        self.seller_conn = conn
        conn.sendall(b"Your role is: [Seller]\nPlease submit auction request:\n")   # Assigning role to the client
        self.status = 1     # Setting status to 1 so that the new clients can join as buyers

        while True:
            try:
                data = conn.recv(1024).decode() # Receive auction details from seller
                if not data:
                    break
                auction_details = data.split()
                if len(auction_details) != 4:   # Ensure exactly four components are received
                    raise Exception()
                
                auc_type, auc_min_price, max_bids, item_name = auction_details

                if (auc_type.isdigit() and auc_min_price.isdigit() and max_bids.isdigit() and int(auc_type) <= 2 and int(auc_type) > 0):
                    # Store validated details in the dictionary
                    self.auction_details = {
                        'auc_type': int(auc_type),  # Type 1 or 2
                        'auc_min_price': int(auc_min_price),    # Minimum price for the auction
                        'max_bids': int(max_bids),      # Maximum number of bids allowed
                        'item_name': str(item_name)     # Name of the item being auctioned
                    }     
                    print(self.auction_details) 
                    print("Action request received. Now waiting for Buyer")
                                  
                    break
                else:
                    raise Exception()
                
            except Exception as e:
                conn.sendall(b"Server: Invalid auction request!\n")     # Notify seller of invalid request format
                continue
                


    def handle_buyer(self, conn, addr):    
        print(">> New Buyer Thread spawned")    # Server log
        conn.sendall(b"Your role is: [Buyer]\n")    # Assigning role Buyer to client

        with self.buyer_lock:   # Acquire lock to safely modify buyers list
            if len(self.buyers) < self.auction_details['max_bids']:
                buyer_number = len(self.buyers) + 1
                buyer_id = f"Buyer {buyer_number}"
                self.buyers.append((conn, buyer_id))    # Add buyer connection and ID to list
                
                print(f"Buyer {buyer_id} is connected from {addr[0]}:{addr[1]}")    # Server log
            
                should_start_bidding = len(self.buyers) == self.auction_details['max_bids']     # Check if max buyers reached
                  
        if should_start_bidding:
            self.start_bidding()    # Starting the bidding process
        else:
            conn.sendall(b"The Auctioneer is still waiting for other Buyer to connect...\n")    # Notify the buyer that the server is waiting for other buyers to connect
            print(f"Buyer len = {len(self.buyers)}")


    def start_bidding(self):
        for conn, _, in self.buyers:
            conn.sendall(b"Requested number of bidders arrived. Let's start bidding!\n")    # Notify buyers that server has started bidding process
        self.seller_conn.sendall(b"Requested number of bidders arrived. Let's start bidding!\n")    # Notify seller that server has started bidding process
        print("Requested number of bidders arrived. Let's start bidding!")      # Server log
        self.ongoing = True

        threads = []
        for conn, buyer_id in self.buyers:
            thread = threading.Thread(target=self.receive_bid, args=(conn, buyer_id))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        self.determine_winner()
    

    def receive_bid(self, conn, buyer_id):
        while True:
            conn.sendall(b"Please submit your bid:")
            data = conn.recv(1024).decode()
            if data:
                try:
                    bid_amount = int(data)
                    if bid_amount < 0:
                        conn.sendall(b"Server: Invalid bid. Please submit a positive integer")
                        continue
                    print(f"bid: {bid_amount}")
                    with self.buyer_lock:
                        print("Lock acquired")
                        self.bids[buyer_id] = bid_amount
                        print(f"{buyer_id} bid ${bid_amount}")
                        conn.sendall(b"Bid receive. Please wait...\n")
                        break
                except ValueError:
                    conn.sendall(b"Invalid bid.\n")

    def determine_winner(self):
        with self.buyer_lock:
            highest_bidder_id = max(self.bids, key=self.bids.get)
            highest_bid = self.bids[highest_bidder_id]

            if highest_bid >= self.auction_details['auc_min_price']:
                if self.auction_details['auc_type'] == 1:
                    self.notify_winner(highest_bidder_id, highest_bid)
                elif self.auction_details['auc_type'] == 2:
                    second_highest_bid = sorted(self.bids.values(), reverse=True)[1]
                    self.notify_winner(highest_bidder_id, second_highest_bid)
            else:
                self.notify_no_sale()

    def notify_winner(self, winner_id, price):
        winner_conn = next(conn for conn, buyer_id in self.buyers if buyer_id == winner_id)

        winner_conn.sendall(f"You won this item {self.auction_details['item_name']}. Your payment due is ${price}".encode())
        self.seller_conn.sendall(f"Success! Your item {self.auction_details['item_name']} has been sold for ${price}".encode())

        print(f"The item was sold to {winner_id} for ${price}")

        for conn, buyer_id in self.buyers:
            if buyer_id != winner_id:
                conn.sendall(b"Unfortunately, you did not win in the last round.\n")
        
        self.reset_server()

    def notify_no_sale(self):
        for conn, _ in self.buyers:
            conn.sendall(b"The item was not sold.\n")
        
        print("The item was not sold")
        self.reset_server()
    

    def reset_server(self):
        self.status = 0
        self.auction_details = None
        self.ongoing = False

        if self.seller_conn:
            self.seller_conn.close()
            print("Conn closed with seller")
        self.seller_conn = None
        for conn, buyer_id in self.buyers:
            conn.close()
            print(f"Conn closed with {buyer_id}")
        with self.buyer_lock:
            self.buyers.clear()
            self.bids.clear()
        


if __name__ == "__main__":

    try:
        parser = argparse.ArgumentParser(description="Add host IP address and host port")
        parser.add_argument('host', type=str, help="The host IP address")
        parser.add_argument('port', type=int, help="The host IP address")

        args = parser.parse_args()

        host = args.host
        port = args.port

        server = AuctioneerServer(host, port)
        server.start_server()
    except Exception as e:
        print(f"Error: {e}")