import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox
from client import Client 
import threading


class ChatApp(tk.Tk):
    def __init__(self, client):
        super().__init__()
        self.client = client

        self.title("Chat Application")
        self.geometry("400x400")
        
        self.connect_button = tk.Button(self, text="Connect", command=self.connect_to_server)
        self.connect_button.pack(padx=20, pady=5)

        
   
    def connect_to_server(self):
        host = 'localhost'  #use a dialog to get these values if needed - TODO: set up connection by filling in the host and port
        port = 12345
        self.client.start_client(host, port)
    
        self.connect_button.pack_forget() #gets rid of it
        self.setup_login_ui() #prompt for login
        

    def setup_login_ui(self):
        # Setup UI for login
        self.login_frame = tk.Frame(self)
        self.login_frame.pack(padx=20, pady=20)

        self.username_label = tk.Label(self.login_frame, text="Username:")
        self.username_label.pack()
        self.username_entry = tk.Entry(self.login_frame)
        self.username_entry.pack()
        self.username_entry.focus_set() #hit tab to go to the next login screen

        self.password_label = tk.Label(self.login_frame, text="Password:")
        self.password_label.pack()
        self.password_entry = tk.Entry(self.login_frame, show="*")
        self.password_entry.pack()

        self.login_button = tk.Button(self.login_frame, text="Login", command=lambda: self.handle_login(existing="yes"))
        self.login_button.pack()

        self.create_account_button = tk.Button(self.login_frame, text="Create Account", command=lambda: self.handle_login(existing="no"))
        self.create_account_button.pack()

        self.message_label = tk.Label(self.login_frame, text="")
        self.message_label.pack()
        
            

    def handle_login(self, existing): 
        #todo: fix bug on duplicate username timeout
        username = self.username_entry.get()
        password = self.password_entry.get()

        if username and password: 
            message = self.client.handle_login(username, password, existing)
            self.message_label.config(text=message) 
            self.display_pending_messages()
        



    def display_pending_messages(self):
        message_frame = tk.Frame(self)
        message_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        # Text area for displaying messages
        self.text_area = scrolledtext.ScrolledText(message_frame)
        self.text_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = tk.Frame(message_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # 'More' button on the left
        more_button = tk.Button(button_frame, text="More", command=self.request_more_messages, width=10, height=2)
        more_button.pack(side=tk.LEFT, padx=10, pady=10)
        

        done_button = tk.Button(button_frame, text="Done", command=self.proceed_to_chat, width=10, height=2)  # Match the style
        done_button.pack(side=tk.RIGHT, padx=10, pady=10)


        messages = self.client.get_pending_messages()
        self.text_area.insert(tk.END, messages)



    def request_more_messages(self):
        """ Sends request for more messages and updates the text area. """
        more_messages = self.client.grab_more_messages()
        self.text_area.insert(tk.END, more_messages + "\n")


    def set_recipient(self, event=None):
        recipient = self.recipient_entry.get()
        if recipient:
            self.client.set_recipient(recipient)  # Ensure this method is implemented in your client class
            self.text_area.insert(tk.END, f"Now messaging: {recipient}\n")




    def proceed_to_chat(self):
        self.login_frame.pack_forget()  # Remove the login frame
        self.text_area.delete(1.0, tk.END)  # Clear the text area

        # Prompt for selecting a user to message
        self.recipient_label = tk.Label(self, text="Who would you like to message?")
        self.recipient_label.pack(padx=20, pady=5)

        self.recipient_frame = tk.Frame(self, bd=2, relief=tk.SOLID, bg="blue")
        self.recipient_frame.pack(padx=20, pady=5, fill=tk.X)

        self.recipient_entry = tk.Entry(self.recipient_frame, width=50)
        self.recipient_entry.pack(padx=2, pady=2)
        self.recipient_entry.bind("<Return>", self.set_recipient)
        

        # Entry box for typing messages
        self.msg_entry = tk.Entry(self, width=50)
        self.msg_entry.pack(padx=20, pady=5)

        # Send button
        self.send_button = tk.Button(self, text="Send", command=self.send_message, width=20, height=2)
        self.send_button.pack(padx=20, pady=5)

        self.delete_button = tk.Button(self, text="Delete Account", command=self.delete_account, width=10, height=2)
        self.delete_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.list_button = tk.Button(self, text="List", command=self.list_accounts, width=10, height=2)
        self.list_button.pack(side=tk.LEFT, padx=10, pady=10)


        self.delete_message_button = tk.Button(self, text="Delete message", command=self.delete_message, width=10, height=2)
        self.delete_message_button.pack(side=tk.LEFT, padx=10, pady=10)

        #Quit/logout button
        self.quit_button = tk.Button(self, text="Logout", command=self.quit_app)
        self.quit_button.pack(padx=20, pady=5)

        # Start a thread to receive messages
        threading.Thread(target=self.receive_messages, daemon=True).start()




    def delete_account(self): 

        #todo: specify that it is up to the user to check if they want to read their messages or not
        
        confirmation = messagebox.askyesno("Delete Account", "Are you sure you want to delete your account? You may have unread messages!")
        if not confirmation:
            return

        server_message = self.client.delete_account()
        self.text_area.insert(tk.END, server_message + '\n')
        self.quit_app()




    def list_accounts(self): 
        accounts = self.client.list_accounts()
        accounts_window = tk.Toplevel(self)
        accounts_window.title("List of users you can message:")
        accounts_window.geometry("300x200")

        accounts_text = scrolledtext.ScrolledText(accounts_window, wrap=tk.WORD)
        accounts_text.pack(expand=True, fill=tk.BOTH)

        for account in accounts:
            accounts_text.insert(tk.END, account + "\n")

        # Search entry and button
        search_frame = tk.Frame(accounts_window)
        search_frame.pack(pady=10)

        search_label = tk.Label(search_frame, text="Search by pattern:")
        search_label.pack(side=tk.LEFT, padx=5)

        search_entry = tk.Entry(search_frame)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<Return>", lambda event: self.search_accounts(search_entry, accounts, search_frame))

        
    def search_accounts(self, search_entry, accounts, search_frame):
        search_result = self.client.wildcard(search_entry.get(), accounts)
        search_result_text = "\n".join(search_result)

        if hasattr(self, 'result_text'):
            self.result_text.delete(1.0, tk.END)
        else:
            result_label = tk.Label(search_frame, text="Search Results:")
            result_label.pack(side=tk.LEFT, padx=5)

            self.result_text = tk.Text(search_frame, height=5, width=30)
            self.result_text.pack(side=tk.LEFT, padx=5)

        self.result_text.insert(tk.END, search_result_text)



    def delete_message(self):
        #grab text by lines 
        text_content = self.text_area.get("1.0", tk.END).strip()
        lines = text_content.split("\n")
        last_message = lines[-1]
        # print(last_message)
        
        self.client.delete_message(last_message)
        self.text_area.delete("end-2l", "end-1l")
    # else:
    #     messagebox.showinfo("No Messages", "There are no messages to delete.")



    def send_message(self, event=None):
        recipient = self.recipient_entry.get()
        message = self.msg_entry.get()
        
        self.text_area.insert(tk.END, "You: " + message + '\n')
        self.client.send_messages(recipient, message)  # Ensure this method is adapted to handle GUI


    def receive_messages(self):
        while self.client.connected:
            message = self.client.receive_messages()
        
            self.text_area.insert(tk.END, "Recieved from: " + message + '\n')


    def quit_app(self):
        self.client.close_connection()
        self.destroy()


    def mainloop(self):
        tk.mainloop()
        


if __name__ == "__main__":
    client = Client()
    app = ChatApp(client)
    app.mainloop()


# #this works 
# if __name__ == "__main__":
#     host = 'localhost'  
#     port = 12345
#     client = Client()  
#     client.start_client(host, port)
#     client.handle_login()
#     while client.handle_action(): 
#         pass















#if we ever want to connect over harvard public wifi, uncomment this here and in server code
# if __name__ == "__main__":
#     # server_ip = input("Enter the server IP address: ")
#     # start_client(server_ip)
#     start_client()


