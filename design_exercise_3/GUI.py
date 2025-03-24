import tkinter as tk
import threading
from tkinter import scrolledtext, messagebox
from tkinter import font as tkfont
from client import Client


class ChatApp(tk.Tk):
    """
    A Tkinter-based GUI client application enabling message-based communication.

    This class manages:
      - A connection screen for specifying host and port, and establishing connection
      - A login screen for existing users and account creation for new users
      - A display of any pending (unread) messages
      - A main chat interface for composing, sending, receiving, and deleting messages
      - Deleting an account from the server
      - Listing/searching all registered accounts
      - Logging out/closing the application
    """

    def __init__(self, client):
        """
        Fire up the connection screen with host/port entries and a connect button.
        
        :param client: An instance of the Client class responsible for socket communication.
        """
        super().__init__()
        self.client = client

        # Window title and basic geometry
        self.title("Welcome to Sav and Ian's Messaging App!")
        self.minsize(600, 800)
        self.configure(bg="light blue")

        # Styling the labels, entries, and buttons using tkfont
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)
        button_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

        # Create a frame to hold connection settings
        connection_frame = tk.Frame(self, bg="light blue", pady=40)
        connection_frame.pack(fill=tk.X, padx=20)

        # Host label and entry
        self.host_label = tk.Label(connection_frame, text="Host:", font=label_font, bg="light blue")
        self.host_label.pack(side=tk.LEFT, padx=10)

        self.host_entry = tk.Entry(
            connection_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black"
        )
        self.host_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)

        # Port label and entry
        self.port_label = tk.Label(connection_frame, text="Port:", font=label_font, bg="light blue")
        self.port_label.pack(side=tk.LEFT, padx=10)

        self.port_entry = tk.Entry(
            connection_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black"
        )
        self.port_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)

        # Connect button that attempts the connection
        self.connect_button = tk.Button(
            self,
            text="Connect",
            command=self.attempt_connection,
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2
        )
        self.connect_button.pack(pady=20)


    def attempt_connection(self):
        """
        Tries user-supplied connection info (host and port) against the server's socket.
        If it fails, the user is prompted to try again.

        Retrieves values from host_entry and port_entry, attempts casting the port to int,
        and starts the client if valid. If unsuccessful, displays an error dialog.
        """
        host = self.host_entry.get()
        port_text = self.port_entry.get()

        try:
            port = int(port_text)
            # Attempt to start the client with user-supplied host and port
            self.client.start_client(host, port)
            # If successful, move on to the login interface
            self.setup_login_ui()

        except Exception as e:
            # Prompt user to try again on connection failure
            messagebox.showerror("Connection Error", "Invalid host or port. Please try again.")


    def setup_login_ui(self):
        """
        Sets up the login screen for the client.
        
        Removes the connect button and displays username/password entry fields,
        as well as 'Login' and 'Create Account' buttons.
        """
        # Remove the connect button
        self.connect_button.pack_forget()

        # Create a frame for login widgets
        self.login_frame = tk.Frame(self, bg="light blue")
        self.login_frame.pack(padx=20, pady=20)

        # Basic styling setup for labels, entries, and buttons
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)
        button_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

        # Username label and entry
        self.username_label = tk.Label(self.login_frame, text="Username:", font=label_font, bg="light blue")
        self.username_label.pack()

        self.username_entry = tk.Entry(
            self.login_frame,
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black"
        )
        self.username_entry.pack()
        self.username_entry.focus_set()  # Focus on the username entry first

        # Password label and entry
        self.password_label = tk.Label(self.login_frame, text="Password:", font=label_font, bg="light blue")
        self.password_label.pack()

        self.password_entry = tk.Entry(
            self.login_frame,
            show="*",
            font=entry_font,
            highlightbackground="black",
            highlightthickness=1,
            highlightcolor="black"
        )
        self.password_entry.pack()

        # 'Login' button
        self.login_button = tk.Button(
            self.login_frame,
            text="Login",
            command=lambda: self.handle_login(existing="yes"),
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2
        )
        self.login_button.pack()

        # 'Create Account' button
        self.create_account_button = tk.Button(
            self.login_frame,
            text="Create Account",
            command=lambda: self.handle_login(existing="no"),
            fg="black",
            font=button_font,
            relief=tk.RAISED,
            bd=5,
            width=20,
            height=2
        )
        self.create_account_button.pack()

        # Label to display messages (e.g. errors, confirmations)
        self.message_label = tk.Label(self.login_frame, text="", font=label_font, bg="light blue")
        self.message_label.pack()


    def handle_login(self, existing):
        """
        Grabs the user-supplied login credentials and ships them off to the server for validation.
        
        :param existing: A string flag ("yes" or "no") indicating whether the user is trying to log in 
                         to an existing account ("yes") or create a new account ("no").
        """
        username = self.username_entry.get()
        password = self.password_entry.get()

        # Basic validation of user input
        if not username or not password:
            self.message_label.config(text="Please enter both username and password.")
            return

        # Attempt login / account creation
        success_flag, message = self.client.handle_login(username, password, existing)

        if success_flag:
            # If the login was successful, display message and show pending messages screen
            self.message_label.config(text=message)
            self.display_pending_messages()
        else:
            # If unsuccessful, clear fields and instruct user to try again
            self.username_entry.delete(0, 'end')
            self.password_entry.delete(0, 'end')
            self.message_label.config(text=message)


    def display_pending_messages(self):
        """
        Set up the display screen for pending messages and format them.
        
        Shows a ScrolledText widget containing unread messages, with 'More' and 'Done' buttons
        for requesting additional messages from the server and proceeding to the main chat, respectively.
        """
        # Create a frame to hold the messages
        self.message_frame = tk.Frame(self)
        self.message_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        # Create a scrolled text area to display the messages
        self.text_area = scrolledtext.ScrolledText(self.message_frame, font=("Helvetica", 14))
        self.text_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Create another frame to hold the 'More' and 'Done' buttons
        self.button_frame = tk.Frame(self)
        self.button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # 'More' button to request additional unread messages
        self.more_button = tk.Button(
            self.button_frame,
            text="More",
            command=self.request_more_messages,
            width=10,
            height=2
        )
        self.more_button.pack(side=tk.LEFT, padx=10, pady=10)

        # 'Done' button to proceed to the main chat screen
        self.done_button = tk.Button(
            self.button_frame,
            text="Done",
            command=self.proceed_to_chat,
            width=10,
            height=2
        )
        self.done_button.pack(side=tk.RIGHT, padx=10, pady=10)

        # Retrieve and display the initial batch of pending messages
        messages = self.client.get_pending_messages()
        self.text_area.insert(tk.END, messages)


    def request_more_messages(self):
        """
        Sends a request for more messages and updates the text area with any new messages.
        
        Uses the client's 'grab_more_messages' method to fetch additional unread messages.
        """
        more_messages = self.client.grab_more_messages()
        self.text_area.insert(tk.END, more_messages + "\n")


    def proceed_to_chat(self):
        """
        Takes the user from the pending messages screen to the main chat screen.
        
        Sets up the interface for selecting a recipient, composing messages, sending, etc.
        Spawns a thread to continuously listen for incoming messages.
        """
        # Clear the text area and remove the login frame
        self.text_area.delete("1.0", tk.END)
        self.login_frame.pack_forget()

        # Label for choosing a recipient
        self.recipient_label = tk.Label(self, text="Who would you like to message?", bg="light blue")
        self.recipient_label.pack(padx=20, pady=5)

        # Frame for recipient entry
        self.recipient_frame = tk.Frame(self, bd=2, relief=tk.SOLID)
        self.recipient_frame.pack(padx=20, pady=5, fill=tk.X)

        # Entry where user specifies the recipient's username
        self.recipient_entry = tk.Entry(self.recipient_frame, width=50)
        self.recipient_entry.pack(padx=2, pady=2)
        self.recipient_entry.bind("<Return>", self.set_recipient)  # Hitting Enter sets the recipient

        # Frame for composing the message
        self.msg_frame = tk.Frame(self, bd=2, relief=tk.SOLID)
        self.msg_frame.pack(padx=20, pady=5, fill=tk.X)

        self.msg_entry = tk.Entry(self.msg_frame, width=50)
        self.msg_entry.pack(padx=20, pady=5)

        # 'Send' button to transmit the typed message
        button_font = tkfont.Font(family="Helvetica", size=14)
        self.send_button = tk.Button(
            self,
            text="Send",
            command=self.send_message,
            width=20,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black"
        )
        self.send_button.pack(padx=20, pady=5)

        # Frame for additional controls (delete account, list accounts, delete message, logout)
        button_frame = tk.Frame(self, bg="light blue")
        button_frame.pack(side=tk.BOTTOM, pady=10)

        # 'Delete Account' button
        self.delete_button = tk.Button(
            button_frame,
            text="Delete Account",
            command=self.delete_account,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black"
        )
        self.delete_button.pack(side=tk.LEFT, padx=10)

        # 'List' button to display all registered accounts
        self.list_button = tk.Button(
            button_frame,
            text="List",
            command=self.list_accounts,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black"
        )
        self.list_button.pack(side=tk.LEFT, padx=10)

        # 'Delete message' button to remove the last message from the chat area
        self.delete_message_button = tk.Button(
            button_frame,
            text="Delete message",
            command=self.delete_message,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black"
        )
        self.delete_message_button.pack(side=tk.LEFT, padx=10)

        # 'Logout' button
        self.quit_button = tk.Button(
            button_frame,
            text="Logout",
            command=self.quit_app,
            width=10,
            height=2,
            font=button_font,
            highlightbackground="black",
            highlightcolor="black"
        )
        self.quit_button.pack(side=tk.LEFT, padx=10)

        # Remove the 'More' and 'Done' buttons after proceeding to main chat
        self.more_button.pack_forget()
        self.done_button.pack_forget()

        # Start a daemon thread to listen for incoming messages in the background
        threading.Thread(target=self.receive_messages, daemon=True).start()


    def set_recipient(self, event=None):
        """
        Sets the recipient for outgoing messages.
        
        Sends the selected recipient to the server, so the server knows which socket 
        should receive the forwarded messages.
        
        :param event: An optional event parameter (used when bound to <Return>).
        """
        recipient = self.recipient_entry.get()
        if recipient:
            self.client.set_recipient(recipient)
            self.text_area.insert(tk.END, f"Now messaging: {recipient}\n")


    def delete_account(self):
        """
        Manage account deletion semantics. Prompt user to confirm.
        If confirmed, instruct the server to delete the account, then quit the app.
        """
        confirmation = messagebox.askyesno("Delete Account", "Are you sure you want to delete your account? You may have unread messages!")
        if not confirmation:
            return

        # Send a message to the server to delete the account and close the GUI
        server_message = self.client.delete_account()
        self.text_area.insert(tk.END, server_message + "\n")
        self.quit_app()


    def list_accounts(self):
        """
        Displays all accounts currently registered on the server in a new window.
        Provides a search field to filter accounts by pattern.
        """
        accounts = self.client.list_accounts()

        # Create a new window to show the list of accounts
        accounts_window = tk.Toplevel(self)
        accounts_window.title("List of users you can message:")
        accounts_window.geometry("600x400")

        # Styling for the text area
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)

        # Scrolled text area to display the accounts
        accounts_text = scrolledtext.ScrolledText(accounts_window, wrap=tk.WORD, font=entry_font)
        accounts_text.pack(expand=True, fill=tk.BOTH)

        # Insert the accounts line by line
        for account in accounts:
            accounts_text.insert(tk.END, account + "\n")

        # Create a frame for the search feature
        search_frame = tk.Frame(accounts_window)
        search_frame.pack(pady=10)

        # Label and entry field for searching
        search_label = tk.Label(search_frame, text="Search by pattern:", font=label_font)
        search_label.pack(side=tk.LEFT, padx=5)

        search_entry = tk.Entry(search_frame, font=entry_font)
        search_entry.pack(side=tk.LEFT, padx=5)
        # Bind the Return key to initiate the search
        search_entry.bind("<Return>", lambda event: self.search_accounts(search_entry, search_frame))


    def search_accounts(self, search_entry, search_frame):
        """
        Allows for wildcard searching through registered accounts.
        
        :param search_entry: The Entry widget from which the search pattern is retrieved.
        :param search_frame: The frame in which the search results will be displayed.
        """
        label_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        entry_font = tkfont.Font(family="Helvetica", size=14)

        # Grab the user's search pattern
        pattern = search_entry.get()
        # Filter the accounts based on this pattern
        filtered_accounts = self.client.list_accounts(filter=pattern)

        # If result_text widget already exists, clear it before inserting new results
        if hasattr(self, "result_text"):
            self.result_text.delete(1.0, tk.END)
        else:
            # Label for search results
            result_label = tk.Label(search_frame, text="Search Results:", font=label_font)
            result_label.pack(side=tk.LEFT, padx=5)

            # A Text widget for displaying the search results
            self.result_text = tk.Text(search_frame, height=5, width=30, font=entry_font)
            self.result_text.pack(side=tk.LEFT, padx=5)

        # Insert the filtered account list, one per line
        self.result_text.insert(tk.END, "\n".join(filtered_accounts))


    def delete_message(self):
        """
        Deletes the last message from the chat box (GUI side only).
        
        Since server-side message storage is not used in this implementation, 
        removal here simply clears the last line from the ScrolledText widget.
        """
        # Retrieve the content of the text area
        text_content = self.text_area.get("1.0", tk.END).strip()

        # If there is no content, show a message box
        if not text_content:
            messagebox.showinfo("No Messages", "There are no messages to delete.")
            return

        # Split lines; if there's only one line or none, there's nothing to delete
        lines = text_content.split("\n")
        if len(lines) <= 1:
            messagebox.showinfo("No Messages", "There are no messages to delete.")
            return

        # The last line is the most recent message
        last_message = lines[-1] if lines else ""

        if not last_message:
            # No message to delete
            messagebox.showinfo("No Messages", "There are no messages to delete.")
            return

        # Delete the last line from the text area
        self.text_area.delete("end-2l", "end-1l")


    def send_message(self, event=None):
        """
        Sends the user's composed message to the server for forwarding to the recipient.
        
        :param event: An optional event parameter (used when bound to <Return>).
        """
        recipient = self.recipient_entry.get()
        message = self.msg_entry.get()

        # Display the sent message in the text area
        self.text_area.insert(tk.END, "You: " + message + "\n")

        # Instruct the client to forward the message to the server
        self.client.send_messages(recipient, message)


    def receive_messages(self):
        """
        Continuously listens for incoming messages from the server.
        
        This method runs in a separate daemon thread. Whenever a message arrives,
        it updates the text area with the new message and scrolls to the end.
        """
        for msg in self.client.ReceiveMessages():
            self.text_area.insert(tk.END, msg + "\n")
            self.text_area.see(tk.END)


    def quit_app(self):
        """
        Shuts down the GUI window, effectively logging out the user.
        
        Destroys the Tk root window and stops main event loop.
        """
        self.destroy()


    def mainloop(self):
        """
        Runs the main loop of the GUI, handling all Tkinter events and updates.
        """
        tk.mainloop()


if __name__ == "__main__":
    """
    Assigns the client, initializes the GUI, and runs the main loop.
    
    This is the entry point of the script, creating a Client object 
    with default host/port and passing it to the ChatApp.
    """
    client = Client(host="localhost", port=50051)  # Adjust host and port as needed
    app = ChatApp(client)
    app.mainloop()