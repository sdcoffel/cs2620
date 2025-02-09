import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox
from client import Client  # This would be your client class that handles network operations
import threading


# class ChatApp(tk.Tk):
#     def __init__(self, client):
#         super().__init__()
#         self.client = client

#         self.title("Chat Application")
#         self.geometry("400x400")
        
#         self.connect_button = tk.Button(self, text="Connect", command=self.connect_to_server)
#         self.connect_button.pack(padx=20, pady=5)


#     def setup_login_ui(self):
#         # Setup UI for login
#         self.login_frame = tk.Frame(self)
#         self.login_frame.pack(padx=20, pady=20)

#         tk.Label(self.login_frame, text="Username:").pack()
#         self.username_entry = tk.Entry(self.login_frame)
#         self.username_entry.pack()

#         tk.Label(self.login_frame, text="Password:").pack()
#         self.password_entry = tk.Entry(self.login_frame, show="*")
#         self.password_entry.pack()

#         self.login_button = tk.Button(self.login_frame, text="Login", command=self.handle_login)
#         self.login_button.pack()



#         # # Message display area
#         # self.messages_frame = scrolledtext.ScrolledText(self)
#         # self.messages_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

#         # self.msg_entry = tk.Entry(self, width=50)
#         # self.msg_entry.pack(padx=20, pady=5)
#         # self.msg_entry.bind("<Return>", self.send_message)


#         # self.send_button = tk.Button(self, text="Send", command=self.send_message)
#         # self.send_button.pack(padx=20, pady=5)
        
#         # self.quit_button = tk.Button(self, text="Quit", command=self.quit_app)
#         # self.quit_button.pack(padx=20, pady=5)
        

        
#     def connect_to_server(self):
#         host = 'localhost'  # Use a dialog to get these values if needed
#         port = 12345
#         self.client.start_client(host, port)
#         if self.client.connected:
#             threading.Thread(target=self.receive_messages, daemon=True).start()
#             self.connect_button.pack_forget() #gets rid of it
#             self.setup_login_ui() #prompt for login

#         else:
#             tk.messagebox.showerror("Connection Failed", "Could not connect to the server.")


#     def setup_login_ui(self):
#             # Setup UI for login
#             self.login_frame = tk.Frame(self)
#             self.login_frame.pack(padx=20, pady=20)

#             tk.Label(self.login_frame, text="Username:").pack()
#             self.username_entry = tk.Entry(self.login_frame)
#             self.username_entry.pack()

#             tk.Label(self.login_frame, text="Password:").pack()
#             self.password_entry = tk.Entry(self.login_frame, show="*")
#             self.password_entry.pack()

#             self.login_button = tk.Button(self.login_frame, text="Login", command=self.handle_login)
#             self.login_button.pack()
            

#     def handle_login(self):
#         username = self.username_entry.get()
#         password = self.password_entry.get()
#         # hashed_password = self.client.hash_password(password)

#         # credentials = f"{username},{hashed_password},yes"  # Assume 'yes' for existing user
#         # self.client.send_credentials(credentials)

#         # # Wait and check server response
#         # server_message = self.client.receive_server_message()
#         # if "Success" in server_message or "Account created" in server_message:
#         #     messagebox.showinfo("Login Success", "You are logged in.")
#         #     self.after_login()
#         # else:
#         #     messagebox.showerror("Login Failed", server_message)




#     # def send_message(self, event=None):
#     #     message = self.msg_entry.get()
#     #     if message:
#     #         self.client.send_messages(message)  # Ensure this method is adapted to handle GUI
#     #         self.messages_frame.insert(tk.END, "You: " + message + '\n')
#     #         self.msg_entry.delete(0, tk.END)


#     def receive_messages(self):
#         while self.client.connected:
#             message = self.client.receive_messages()
#             if message:
#                 self.messages_frame.insert(tk.END, message + '\n')


#     def mainloop(self):
#         tk.mainloop()
        

#     # def quit_app(self):
#     #     self.client.close_connection()
#     #     self.destroy()

# if __name__ == "__main__":
#     client = Client()
#     app = ChatApp(client)
#     app.mainloop()

if __name__ == "__main__":
    host = 'localhost'  # Use a dialog to get these values if needed
    port = 12345
    client = Client()  
    client.start_client(host, port)


















#if we ever want to connect over harvard public wifi, uncomment this here and in server code
# if __name__ == "__main__":
#     # server_ip = input("Enter the server IP address: ")
#     # start_client(server_ip)
#     start_client()


