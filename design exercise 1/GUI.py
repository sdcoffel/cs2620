import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox
from tkinter import font as tkfont
from client import Client
import threading
import socket

# these are the connection credentials for my laptop
# host = 'localhost'
# port = 12345


class ChatApp(tk.Tk):
    def __init__(self, client):
        super().__init__()
        self.client = client

        self.title("Welcome to WallyChat!")
        self.minsize(600, 800)
        # self.geometry("600x600")
        self.configure(bg="light blue")

        # Styling variables
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)
        button_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

        # Frame for connection settings
        connection_frame = tk.Frame(self, bg="light blue", pady=40)
        connection_frame.pack(fill=tk.X, padx=20)

        self.host_label = tk.Label(
            connection_frame, text="Host:", font=label_font, bg="light blue"
        )
        self.host_label.pack(side=tk.LEFT, padx=10)
        self.host_entry = tk.Entry(
            connection_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black",
        )
        self.host_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)

        self.port_label = tk.Label(
            connection_frame, text="Port:", font=label_font, bg="light blue"
        )
        self.port_label.pack(side=tk.LEFT, padx=10)
        self.port_entry = tk.Entry(
            connection_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black",
        )
        self.port_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)

        # Connect button
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
        host = self.host_entry.get()
        port_text = self.port_entry.get()

        try:
            #the port number assigned for listening is currently hardcoded in. i don't know if this is bad or not.
            #if you give it a good IP address but port that is not equal to the hardcoded version, it will crash
            port = int(port_text) 
            self.client.start_client(host, port)
            self.setup_login_ui()

        except Exception as e: 
            messagebox.showerror("Connection Error", "Invalid host or port. Please try again.")



    def setup_login_ui(self):
        # Setup UI for login
        self.connect_button.pack_forget()  # gets rid of it
        self.login_frame = tk.Frame(self, bg="light blue")
        self.login_frame.pack(padx=20, pady=20)
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)
        button_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

        self.username_label = tk.Label(
            self.login_frame, text="Username:", font=label_font, bg="light blue"
        )
        self.username_label.pack()
        self.username_entry = tk.Entry(
            self.login_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black",
        )
        self.username_entry.pack()
        self.username_entry.focus_set()  # hit tab to go to the next login screen

        self.password_label = tk.Label(
            self.login_frame, text="Password:", font=label_font, bg="light blue"
        )
        self.password_label.pack()
        self.password_entry = tk.Entry(
            self.login_frame,
            show="*",
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black",
        )
        self.password_entry.pack()

        self.login_button = tk.Button(
            self.login_frame,
            text="Login",
            command=lambda: self.handle_login(existing="yes"),
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2,
        )
        self.login_button.pack()

        self.create_account_button = tk.Button(
            self.login_frame,
            text="Create Account",
            command=lambda: self.handle_login(existing="no"),
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2,
        )
        self.create_account_button.pack()

        self.message_label = tk.Label(
            self.login_frame, text="", font=label_font, bg="light blue"
        )
        self.message_label.pack()

    def handle_login(self, existing):
        # todo: fix bug on duplicate username timeout
        username = self.username_entry.get()
        password = self.password_entry.get()


        # Make sure we have both username and password before proceeding
        if not username or not password:
            self.message_label.config(text="Please enter both username and password.")
            return

        # Attempt to log in (or create account) via the client
        success_flag, message = self.client.handle_login(username, password, existing)

        if success_flag: 
            self.message_label.config(text=message)
            self.display_pending_messages()

        else:
            # If the login was unsuccessful, clear fields and inform the user to try again
            self.username_entry.delete(0, 'end')
            self.password_entry.delete(0, 'end')
            self.message_label.config(text=message)
        # if username and password:
        #     message = self.client.handle_login(username, password, existing) #currently this is the success message
        #     self.message_label.config(text=message)



            #self.display_pending_messages()

    def display_pending_messages(self):
        message_frame = tk.Frame(self)
        message_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        # Text area for displaying messages
        self.text_area = scrolledtext.ScrolledText(
            message_frame, font=("Helvetica", 14)
        )
        self.text_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = tk.Frame(message_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # 'More' button on the left
        more_button = tk.Button(
            button_frame,
            text="More",
            command=self.request_more_messages,
            width=10,
            height=2,
        )
        more_button.pack(side=tk.LEFT, padx=10, pady=10)

        done_button = tk.Button(
            button_frame, text="Done", command=self.proceed_to_chat, width=10, height=2
        )  # Match the style
        done_button.pack(side=tk.RIGHT, padx=10, pady=10)

        messages = self.client.get_pending_messages()
        self.text_area.insert(tk.END, messages)

    def request_more_messages(self):
        """Sends request for more messages and updates the text area."""
        more_messages = self.client.grab_more_messages()
        self.text_area.insert(tk.END, more_messages + "\n")

    def set_recipient(self, event=None):
        recipient = self.recipient_entry.get()
        if recipient:
            self.client.set_recipient(
                recipient
            )  # Ensure this method is implemented in your client class
            self.text_area.insert(tk.END, f"Now messaging: {recipient}\n")

    def proceed_to_chat(self):
        self.login_frame.pack_forget()  # Remove the login frame
        self.text_area.delete(1.0, tk.END)  # Clear the text area

        # Prompt for selecting a user to message
        self.recipient_label = tk.Label(
            self, text="Who would you like to message?", bg="light blue"
        )
        self.recipient_label.pack(padx=20, pady=5)

        self.recipient_frame = tk.Frame(self, bd=2, relief=tk.SOLID)
        self.recipient_frame.pack(padx=20, pady=5, fill=tk.X)

        self.recipient_entry = tk.Entry(self.recipient_frame, width=50)
        self.recipient_entry.pack(padx=2, pady=2)
        self.recipient_entry.bind("<Return>", self.set_recipient)

        # Entry box for typing messages

        self.msg_frame = tk.Frame(self, bd=2, relief=tk.SOLID)
        self.msg_frame.pack(padx=20, pady=5, fill=tk.X)

        self.msg_entry = tk.Entry(self.msg_frame, width=50)
        self.msg_entry.pack(padx=20, pady=5)

        # Send button
        button_font = tkfont.Font(family="Helvetica", size=14)

        self.send_button = tk.Button(
            self,
            text="Send",
            command=self.send_message,
            width=20,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black",
        )
        self.send_button.pack(padx=20, pady=5)

        button_frame = tk.Frame(self, bg="light blue")
        button_frame.pack(side=tk.BOTTOM, pady=10)

        self.delete_button = tk.Button(
            button_frame,
            text="Delete Account",
            command=self.delete_account,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black",
        )
        self.delete_button.pack(side=tk.LEFT, padx=10)

        self.list_button = tk.Button(
            button_frame,
            text="List",
            command=self.list_accounts,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black",
        )
        self.list_button.pack(side=tk.LEFT, padx=10)

        self.delete_message_button = tk.Button(
            button_frame,
            text="Delete message",
            command=self.delete_message,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black",
        )
        self.delete_message_button.pack(side=tk.LEFT, padx=10)

        # Quit/logout button
        self.quit_button = tk.Button(
            button_frame,
            text="Logout",
            command=self.quit_app,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black",
        )
        self.quit_button.pack(side=tk.LEFT, padx=10)

        # Start a thread to receive messages
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def delete_account(self):

        #we specify that it is up to the user to check if they want to read their messages or not
        confirmation = messagebox.askyesno(
            "Delete Account",
            "Are you sure you want to delete your account? You may have unread messages!",
        )
        if not confirmation:
            return

        server_message = self.client.delete_account()
        self.text_area.insert(tk.END, server_message + "\n")
        self.quit_app()

    def list_accounts(self):
        accounts = self.client.list_accounts()
        accounts_window = tk.Toplevel(self)
        accounts_window.title("List of users you can message:")
        accounts_window.geometry("600x400")

        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)

        accounts_text = scrolledtext.ScrolledText(
            accounts_window, wrap=tk.WORD, font=entry_font
        )
        accounts_text.pack(expand=True, fill=tk.BOTH)

        for account in accounts:
            accounts_text.insert(tk.END, account + "\n")

        # Search entry and button
        search_frame = tk.Frame(accounts_window)
        search_frame.pack(pady=10)

        search_label = tk.Label(
            search_frame, text="Search by pattern:", font=label_font
        )
        search_label.pack(side=tk.LEFT, padx=5)

        search_entry = tk.Entry(search_frame, font=entry_font)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind(
            "<Return>",
            lambda event: self.search_accounts(search_entry, accounts, search_frame),
        )

    def search_accounts(self, search_entry, accounts, search_frame):
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)

        search_result = self.client.wildcard(search_entry.get(), accounts)
        search_result_text = "\n".join(search_result)

        if hasattr(self, "result_text"):
            self.result_text.delete(1.0, tk.END)
        else:
            result_label = tk.Label(
                search_frame, text="Search Results:", font=label_font
            )
            result_label.pack(side=tk.LEFT, padx=5)

            self.result_text = tk.Text(
                search_frame, height=5, width=30, font=entry_font
            )
            self.result_text.pack(side=tk.LEFT, padx=5)

        self.result_text.insert(tk.END, search_result_text)

    def delete_message(self):
        # todo: fix the bug that will break if the user keep deleting messages if there are none. also, JSON might have broken this
        # grab text by lines
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

        self.text_area.insert(tk.END, "You: " + message + "\n")
        self.client.send_messages(
            recipient, message
        )  # Ensure this method is adapted to handle GUI

    def receive_messages(self):
        while self.client.connected:
            message = self.client.receive_messages()

            self.text_area.insert(tk.END, "Recieved from: " + message + "\n")

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


# if we ever want to connect over harvard public wifi, uncomment this here and in server code
# if __name__ == "__main__":
#     # server_ip = input("Enter the server IP address: ")
#     # start_client(server_ip)
#     start_client()
