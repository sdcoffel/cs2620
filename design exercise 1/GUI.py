import tkinter as tk
import threading
from tkinter import simpledialog, scrolledtext, messagebox
from tkinter import font as tkfont
from client import Client


class ChatApp(tk.Tk):

    def __init__(self, client):
        """Fire up the connection screen with host/port entries and connect button."""

        super().__init__()

        #client get assigned as the object - wow i love oop so convenient and useful :////////////////!////////!////
        self.client = client

        self.title("Welcome to Sav and Ian's Messaging App!")
        self.minsize(600, 800)
        self.configure(bg="light blue")

        #styling 
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)
        button_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

        #frame for connection settings
        connection_frame = tk.Frame(self, bg="light blue", pady=40)
        connection_frame.pack(fill=tk.X, padx=20)

        #host label and entry frame 
        self.host_label = tk.Label(connection_frame, text="Host:", font=label_font, bg="light blue")
        self.host_label.pack(side=tk.LEFT, padx=10)
        
        self.host_entry = tk.Entry(
            connection_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black")

        self.host_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        self.port_label = tk.Label(connection_frame, text="Port:", font=label_font, bg="light blue")
        self.port_label.pack(side=tk.LEFT, padx=10)
        
        #port label and entry frame 
        self.port_entry = tk.Entry(
            connection_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black")
        
        self.port_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)

        #connect button
        self.connect_button = tk.Button(
            self,
            text="Connect",
            command=self.attempt_connection,
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2)
        
        self.connect_button.pack(pady=20)



    def attempt_connection(self):
        """Tries user supplied connection info against the server's socket. If it fails, user is prompted to try again."""
        host = self.host_entry.get()
        port_text = self.port_entry.get()

        try:
            port = int(port_text) 
            self.client.start_client(host, port)
            self.setup_login_ui()

        except Exception as e: 
            messagebox.showerror("Connection Error", "Invalid host or port. Please try again.")



    def setup_login_ui(self):
        """Sets up the login screen for the client."""

        #get rid of connection buttons and put up login options 
        self.connect_button.pack_forget()  
        self.login_frame = tk.Frame(self, bg="light blue")
        self.login_frame.pack(padx=20, pady=20)
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)
        button_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

        #username styling
        self.username_label = tk.Label(self.login_frame, text="Username:", font=label_font, bg="light blue")
        self.username_label.pack()
        
        self.username_entry = tk.Entry(
            self.login_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black")
        
        self.username_entry.pack()
        self.username_entry.focus_set()  # hit tab to go to the next login screen

        #password styling
        self.password_label = tk.Label(self.login_frame, text="Password:", font=label_font, bg="light blue")
        self.password_label.pack()

        self.password_entry = tk.Entry(
            self.login_frame,
            show="*",
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black")
        self.password_entry.pack()

        #login button styling 
        self.login_button = tk.Button(
            self.login_frame,
            text="Login",
            command=lambda: self.handle_login(existing="yes"),
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2)
        
        self.login_button.pack()

        #account creation styling 
        self.create_account_button = tk.Button(
            self.login_frame,
            text="Create Account",
            command=lambda: self.handle_login(existing="no"),
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2)
        
        self.create_account_button.pack()
        self.message_label = tk.Label(self.login_frame, text="", font=label_font, bg="light blue")
        self.message_label.pack()



    def handle_login(self, existing):
        """Grabs the user-supplied login credentials and ships them off to the server for validation."""

        username = self.username_entry.get()
        password = self.password_entry.get()

        if not username or not password:
            self.message_label.config(text="Please enter both username and password.")
            return

        #login/account creation attempt
        success_flag, message = self.client.handle_login(username, password, existing)

        if success_flag: 
            self.message_label.config(text=message)
            self.display_pending_messages()

        else:
            #if the login was unsuccessful, clear fields and try again
            self.username_entry.delete(0, 'end')
            self.password_entry.delete(0, 'end')
            self.message_label.config(text=message)



    def display_pending_messages(self):
        """Set up the display screen and format the pending messages."""

        #frame to display messages
        self.message_frame = tk.Frame(self)
        self.message_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        #text area for pending messages
        self.text_area = scrolledtext.ScrolledText(self.message_frame, font=("Helvetica", 14))
        self.text_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        #separate frame for buttons
        self.button_frame = tk.Frame(self)
        self.button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        #more button styling 
        self.more_button = tk.Button(
            self.button_frame,
            text="More",
            command=self.request_more_messages,
            width=10,
            height=2)
        
        self.more_button.pack(side=tk.LEFT, padx=10, pady=10)

        #done button styling 
        self.done_button = tk.Button(
            self.button_frame,
            text="Done",
            command=self.proceed_to_chat,
            width=10,
            height=2)
        
        self.done_button.pack(side=tk.RIGHT, padx=10, pady=10)

        messages = self.client.get_pending_messages()
        self.text_area.insert(tk.END, messages)



    def request_more_messages(self):
        """Sends request for more messages and updates the text area."""

        more_messages = self.client.grab_more_messages()
        self.text_area.insert(tk.END, more_messages + "\n")



    def proceed_to_chat(self):
        """Takes the user from the pending messages screen to the main chat screen."""

        #clear the login screen 
        self.login_frame.pack_forget()  
        self.text_area.delete(1.0, tk.END)  

        #recipient styling 
        self.recipient_label = tk.Label(self, text="Who would you like to message?", bg="light blue")
        self.recipient_label.pack(padx=20, pady=5)

        self.recipient_frame = tk.Frame(self, bd=2, relief=tk.SOLID)
        self.recipient_frame.pack(padx=20, pady=5, fill=tk.X)

        self.recipient_entry = tk.Entry(self.recipient_frame, width=50)
        self.recipient_entry.pack(padx=2, pady=2)
        self.recipient_entry.bind("<Return>", self.set_recipient)

        #message entry styling 
        self.msg_frame = tk.Frame(self, bd=2, relief=tk.SOLID)
        self.msg_frame.pack(padx=20, pady=5, fill=tk.X)

        self.msg_entry = tk.Entry(self.msg_frame, width=50)
        self.msg_entry.pack(padx=20, pady=5)

        #send button styling 
        button_font = tkfont.Font(family="Helvetica", size=14)

        self.send_button = tk.Button(
            self,
            text="Send",
            command=self.send_message,
            width=20,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black")
        
        self.send_button.pack(padx=20, pady=5)
        button_frame = tk.Frame(self, bg="light blue")
        button_frame.pack(side=tk.BOTTOM, pady=10)

        #delete account button styling 
        self.delete_button = tk.Button(
            button_frame,
            text="Delete Account",
            command=self.delete_account,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black")
        
        self.delete_button.pack(side=tk.LEFT, padx=10)

        #list button styling 
        self.list_button = tk.Button(
            button_frame,
            text="List",
            command=self.list_accounts,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black")
        
        self.list_button.pack(side=tk.LEFT, padx=10)

        #delete message button styling 
        self.delete_message_button = tk.Button(
            button_frame,
            text="Delete message",
            command=self.delete_message,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black")
        
        self.delete_message_button.pack(side=tk.LEFT, padx=10)

        #logout button styling 
        self.quit_button = tk.Button(
            button_frame,
            text="Logout",
            command=self.quit_app,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black")
        
        self.quit_button.pack(side=tk.LEFT, padx=10)

        #get rid of the more and done buttons 
        self.more_button.pack_forget()
        self.done_button.pack_forget()

        #start a thread to receive messages so multiple clients can run concurrently 
        threading.Thread(target=self.receive_messages, daemon=True).start()



    def set_recipient(self, event=None):
        """Tells the server which recipient the client is trying to message. Helps the server assign the corresponding socket."""

        recipient = self.recipient_entry.get()
        if recipient:
            self.client.set_recipient(recipient)  
            self.text_area.insert(tk.END, f"Now messaging: {recipient}\n")



    def delete_account(self):
        """Manage account deletion semantics. Give the user the option to delete their account or not, if they have unread messages."""
    
        confirmation = messagebox.askyesno("Delete Account", "Are you sure you want to delete your account? You may have unread messages!")
        if not confirmation:
            return

        #send a message to the server to delete the account and close the GUI
        server_message = self.client.delete_account()
        self.text_area.insert(tk.END, server_message + "\n")
        self.quit_app()



    def list_accounts(self):
        """Displays all the accounts that are currently registered on the server, for the user to reference when messaging someone."""

        #window styling 
        accounts = self.client.list_accounts()
        accounts_window = tk.Toplevel(self)
        accounts_window.title("List of users you can message:")
        accounts_window.geometry("600x400")

        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)

        accounts_text = scrolledtext.ScrolledText(accounts_window, wrap=tk.WORD, font=entry_font)
        accounts_text.pack(expand=True, fill=tk.BOTH)

        for account in accounts:
            accounts_text.insert(tk.END, account + "\n")

        #search label and entry styling 
        search_frame = tk.Frame(accounts_window)
        search_frame.pack(pady=10)

        search_label = tk.Label(search_frame, text="Search by pattern:", font=label_font)
        search_label.pack(side=tk.LEFT, padx=5)

        search_entry = tk.Entry(search_frame, font=entry_font)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<Return>", lambda event: self.search_accounts(search_entry, accounts, search_frame))



    def search_accounts(self, search_entry, accounts, search_frame):
        """Allows for wildcard searching through registered accounts."""

        #result styling 
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)
        search_result = self.client.wildcard(search_entry.get(), accounts)

        if isinstance(search_result, list):
            search_result_text = "\n".join(search_result)

        else:
            search_result_text = search_result

        #refresh each attempt on repeated searches 
        if hasattr(self, "result_text"):
            self.result_text.delete(1.0, tk.END)

        else:
            result_label = tk.Label(search_frame, text="Search Results:", font=label_font)
            result_label.pack(side=tk.LEFT, padx=5)
            self.result_text = tk.Text(search_frame, height=5, width=30, font=entry_font)
            self.result_text.pack(side=tk.LEFT, padx=5)

        self.result_text.insert(tk.END, search_result_text)



    def delete_message(self):
        """Deletes messages for the user and removes it from the chat box. Also sends a request to the server to remove the message from its database."""

        #grab text
        text_content = self.text_area.get("1.0", tk.END).strip()
        
        if not text_content:
            messagebox.showinfo("No Messages", "There are no messages to delete.")
            return
        
        #split lines, exclude the line that includes the intended recipient
        lines = text_content.split("\n")
        if len(lines) <= 1: 
            messagebox.showinfo("No Messages", "There are no messages to delete.")
            return
        
        last_message = lines[-1] if lines else ""
        
        if not last_message:
            messagebox.showinfo("No Messages", "There are no messages to delete.")
            return

        #sends request to the server to delete the message and #deletes the last line
        self.client.delete_message(last_message)
        self.text_area.delete("end-2l", "end-1l")



    def send_message(self, event=None):
        """Sends the message to the server for forwarding."""

        recipient = self.recipient_entry.get()
        message = self.msg_entry.get()
        self.text_area.insert(tk.END, "You: " + message + "\n")
        self.client.send_messages(recipient, message)  



    def receive_messages(self):
        """Recieves messages that the server has forwarded."""

        while self.client.connected:
            message = self.client.receive_messages()
            self.text_area.insert(tk.END, "Recieved from: " + message + "\n")



    def quit_app(self):
        """Shuts down the GUI."""

        self.client.close_connection()
        self.destroy()



    def mainloop(self):
        """Runs the main loop of the GUI."""

        tk.mainloop()


if __name__ == "__main__":
    """Assigns the client, GUI, and runs the main loop."""

    client = Client()
    app = ChatApp(client)
    app.mainloop()

