import socket
import json
import yaml
import time

class UDPChatClient(object):
    def __init__(self, client_host, client_port, server_host, server_port):
        self._host = client_host
        self._port = client_port
        self._server_host = server_host
        self._server_port = server_port
        self.username_lookup = dict()

    def __enter__(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self._host, self._port))
        self._sock = sock
        return self

    def __exit__(self,*exc_info):
        if exc_info[0]:
            import traceback
            traceback.print_exception(*exc_info)
        self._sock.close()

    def send_json_to_server(self, json_payload):
        self._sock.sendto(json.dumps(json_payload).encode(), (self._server_host, self._server_port))

    def get_json_incoming(self):
        msg, addr = self._sock.recvfrom(1024)
        try:
            msg_received = json.loads(msg.decode())
            return msg_received
        except:
            return {'status': 'error', 'status_msg': 'json could not be parsed'}

    def get_message(self, user_id):
        payload = {'action': 'get', 'user_id': user_id}
        self.send_json_to_server(payload)
        response = self.get_json_incoming()
        if response.get('status') == 'error':
            print("Error retrieving message for user_id {0}: {1}".format(user_id, response.get('status_msg')))
            return False
        else:
            if 'status_msg' in response and response.get('status_msg') == 'no messages':
                return False
            else:
                sending_user = [username for username, user_id in self.username_lookup.items() 
                                if user_id == response.get('value').get('sender_id')].pop()
                print("{0}: {1}".format(sending_user, response.get('value').get('message')))
                return True                    

    def send_message(self, this_user_id, target_user_id, message):
        payload = {'action': 'send', 'user_id': this_user_id, 'target_user_id': target_user_id, 'message': message}
        self.send_json_to_server(payload)
        response = self.get_json_incoming()
        if response.get('status') == 'error':
            print("Error sending message: {}".format(response.get('status_msg')))
            return False
        else:
            return True

    def get_user_list(self, this_username):
        payload = {'action': 'get_user_list'}
        self.send_json_to_server(payload)
        user_list = self.get_json_incoming()
        user_listing = [user for user in user_list if user != this_username]
        for user in user_listing:
            if user not in self.username_lookup:
                user_id = self.get_user_id(user)
                self.username_lookup[user] = user_id
        return user_listing

    def get_user_id(self, username):
        if username in self.username_lookup:
            return self.username_lookup[username]
        
        self.send_json_to_server({'action': 'get_user_id', 'username': username})
        user_id_query_result = self.get_json_incoming()
        user_id = user_id_query_result.get('value')
        if user_id is None:
            raise ValueError("Couldn't get user id")
        else:
            self.username_lookup[username] = user_id
            return user_id

    def get_this_user_id(self, username):
        if username in self.username_lookup:
            return self.username_lookup[username]
        payload = {'action': 'register', 'username': username}
        self.send_json_to_server(payload)
        # time.sleep(1)
        register_result = self.get_json_incoming()
        if 'status_msg' in register_result:
            if register_result.get('status_msg') == 'User already exists':
                # poll for existing user id
                self.send_json_to_server({'action': 'get_user_id', 'username': username})
                # time.sleep(1)
                user_id_query_result = self.get_json_incoming()
                user_id = user_id_query_result.get('value')
                if user_id is None:
                    raise ValueError("Couldn't get user id")
                else:
                    self.username_lookup[username] = user_id
                    return user_id
            else:
                raise ValueError(register_result)
        else:
            user_id = register_result.get('value')
            self.username_lookup[username] = user_id
            return user_id

def do_help():
    print(("send username [message] -> send user the text message following their username\n" +
           "whoami -> print your username from config.yaml\n" +
           "quit -> quit the client\n" +
           "_ -> anything else will retrieve & print your latest messages & update the available user listing.\n"))

if __name__ == '__main__':
    with open('config.yaml', 'r') as fp:
        options = yaml.load(fp)

    host = options.get('client').get('host') 
    port = options.get('client').get('port')
    server_host = options.get('server').get('host')
    server_port = options.get('server').get('port') 
    username = options.get('client').get('username')

    with UDPChatClient(host, port, server_host, server_port) as client:
        user_id = client.get_this_user_id(username)
        user_list = client.get_user_list(username)
        print("Catching up your message queue...")
        while client.get_message(user_id):
            pass
        while True:
            print("--\nUsers available: {}".format(sorted(user_list) if user_list is not None else []))
            user_input = input("Enter command (h for help): ")
            if user_input == 'h':
                do_help()
            elif user_input.strip() == 'quit':
                break
            elif user_input.strip() == 'whoami':
                print(username)
            elif len(user_input) > 4 and user_input[0:4] == 'send':
                split_user_input = user_input.strip().split(' ')
                if len(split_user_input) < 3:
                    print("Invalid send command, see help.")
                    next
                else:
                    action = split_user_input[0]
                    target_user = split_user_input[1]
                    message = ' '.join(split_user_input[2:])
                    if target_user not in user_list:
                        print("Target user is not in active user list.")
                        next
                    else:
                        target_user_id = client.get_user_id(target_user)
                        client.send_message(user_id, target_user_id, message)
            print("Catching up your message queue...")
            user_list = client.get_user_list(username)
            while client.get_message(user_id):
                pass


