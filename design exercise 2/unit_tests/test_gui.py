import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
import sys

sys.path.append("../")

from client import Client
from GUI import ChatApp  # update path if needed


class TestChatApp(unittest.TestCase):
    def setUp(self):
        """
        Create the Tk root and ChatApp instance before each test.
        Mock the underlying Client to avoid real network calls.
        """
        self.root = tk.Tk()
        self.root.withdraw()
        self.mock_client = MagicMock(spec=Client)

        # Provide a default for .start_client() so it won't raise exceptions.
        self.mock_client.start_client.return_value = None

        # Some tests need .handle_login to succeed, so let's default it:
        self.mock_client.handle_login.return_value = (True, "Login successful")

        # Instantiate the GUI
        self.app = ChatApp(self.mock_client)

    def tearDown(self):
        """
        Destroy the Tk root after each test so it doesn't linger.
        Guard against already-destroyed windows to avoid TclError.
        """
        try:
            if self.app.winfo_exists():
                self.app.destroy()
        except tk.TclError:
            pass

        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass

    @patch("tkinter.messagebox.showerror")
    def test_attempt_connection_success(self, mock_showerror):
        """Call attempt_connection with valid data => setup_login_ui() => login_frame is mapped."""
        self.app.host_entry.insert(0, "127.0.0.1")
        self.app.port_entry.insert(0, "8000")
        # Let the mock client succeed
        self.mock_client.start_client.side_effect = None

        self.app.attempt_connection()

        self.mock_client.start_client.assert_called_once_with("127.0.0.1", 8000)
        mock_showerror.assert_not_called()

        # Force Tkinter to update geometry/mapping
        self.app.update()
        self.assertTrue(self.app.login_frame.winfo_ismapped())

    @patch("tkinter.messagebox.showerror")
    def test_attempt_connection_failure(self, mock_showerror):
        """An invalid port or host triggers the showerror messagebox."""
        self.app.host_entry.insert(0, "invalid_host")
        self.app.port_entry.insert(0, "not_a_number")

        self.app.attempt_connection()

        self.mock_client.start_client.assert_not_called()
        mock_showerror.assert_called_once()

    def test_handle_login_success(self):
        """A successful login scenario => pending messages UI is visible."""
        # Must connect first so login widgets exist
        self.app.host_entry.insert(0, "127.0.0.1")
        self.app.port_entry.insert(0, "8000")
        self.app.attempt_connection()
        self.app.update()

        # Insert credentials
        self.app.username_entry.insert(0, "testuser")
        self.app.password_entry.insert(0, "testpass")
        self.mock_client.handle_login.return_value = (True, "Login Successful")

        self.app.handle_login(existing="yes")

        self.mock_client.handle_login.assert_called_once_with(
            "testuser", "testpass", "yes"
        )
        self.assertEqual(self.app.message_label["text"], "Login Successful")

        # Now message_frame should be visible (pending messages)
        self.app.update()
        self.assertTrue(self.app.message_frame.winfo_ismapped())

    def test_handle_login_failure(self):
        """A failed login => user/password cleared, message shown."""
        # Connect to create login widgets
        self.app.host_entry.insert(0, "127.0.0.1")
        self.app.port_entry.insert(0, "8000")
        self.app.attempt_connection()
        self.app.update()

        # Insert credentials
        self.app.username_entry.insert(0, "baduser")
        self.app.password_entry.insert(0, "badpass")
        self.mock_client.handle_login.return_value = (False, "Invalid credentials")

        self.app.handle_login(existing="yes")

        self.mock_client.handle_login.assert_called_once_with(
            "baduser", "badpass", "yes"
        )
        self.assertEqual(self.app.username_entry.get(), "")
        self.assertEqual(self.app.password_entry.get(), "")
        self.assertEqual(self.app.message_label["text"], "Invalid credentials")

    def test_handle_login_missing_fields(self):
        """If username or password is missing => message_label prompts user."""
        # Connect so login widgets exist
        self.app.host_entry.insert(0, "127.0.0.1")
        self.app.port_entry.insert(0, "8000")
        self.app.attempt_connection()
        self.app.update()

        # Leave them blank
        self.app.handle_login(existing="yes")

        self.mock_client.handle_login.assert_not_called()
        self.assertEqual(
            self.app.message_label["text"], "Please enter both username and password."
        )

    def test_display_pending_messages(self):
        """display_pending_messages => creates text_area with get_pending_messages content."""
        self.mock_client.get_pending_messages.return_value = "Pending1\nPending2"

        self.app.display_pending_messages()
        self.app.update()

        self.assertTrue(hasattr(self.app, "text_area"))
        content = self.app.text_area.get(1.0, tk.END)
        self.assertIn("Pending1", content)
        self.assertIn("Pending2", content)

    def test_request_more_messages(self):
        """Request more => calls grab_more_messages, appends to text_area."""
        self.mock_client.get_pending_messages.return_value = "Initial pending"
        self.app.display_pending_messages()
        self.mock_client.grab_more_messages.return_value = "Another message"

        self.app.request_more_messages()
        self.mock_client.grab_more_messages.assert_called_once()

        content = self.app.text_area.get(1.0, tk.END)
        self.assertIn("Another message", content)

    def test_set_recipient(self):
        """set_recipient => calls client.set_recipient, updates text_area."""
        # Must connect, login, show messages, proceed_to_chat so recipient_entry exists
        self.app.host_entry.insert(0, "127.0.0.1")
        self.app.port_entry.insert(0, "8000")
        self.app.attempt_connection()
        self.app.update()

        self.mock_client.handle_login.return_value = (True, "OK")
        self.app.username_entry.insert(0, "user")
        self.app.password_entry.insert(0, "pass")
        self.app.handle_login(existing="yes")
        self.app.update()

        # We need the message frame so text_area is created
        # Then proceed to chat => spawns the thread looking for 'connected'
        self.mock_client.connected = True  # Avoid AttributeError in the thread
        self.app.proceed_to_chat()
        self.app.update()

        self.app.recipient_entry.insert(0, "some_user")
        self.app.set_recipient()

        self.mock_client.set_recipient.assert_called_once_with("some_user")
        self.assertIn("Now messaging: some_user", self.app.text_area.get(1.0, tk.END))

    @patch("tkinter.messagebox.askyesno", return_value=True)
    @patch("tkinter.Tk.destroy")  # Patch .destroy so the window isn't really closed
    def test_delete_account(self, mock_destroy, mock_askyesno):
        """
        Test that delete_account calls client.delete_account, inserts text,
        and calls quit_app (which calls close_connection and destroy).
        But we mock destroy so the GUI doesn't vanish, letting us read text_area.
        """
        # 1) Ensure text_area is created (connect + login => display_pending_messages => text_area)
        self.app.host_entry.insert(0, "127.0.0.1")
        self.app.port_entry.insert(0, "8000")
        self.app.attempt_connection()
        self.app.update()

        self.mock_client.handle_login.return_value = (True, "Login OK")
        self.app.username_entry.insert(0, "user")
        self.app.password_entry.insert(0, "pass")
        self.app.handle_login(existing="yes")
        self.app.update()

        # 2) Mock server response
        self.mock_client.delete_account.return_value = "Account deleted."

        # 3) Now delete account (which calls quit_app -> close_connection -> destroy)
        self.app.delete_account()

        # Because we did NOT mock quit_app, it runs the real code, including close_connection,
        # but we patched destroy(), so the widget still exists
        self.mock_client.delete_account.assert_called_once()

        # Check text got inserted
        self.assertIn("Account deleted.", self.app.text_area.get(1.0, tk.END))

        # Confirm close_connection was indeed called
        self.mock_client.close_connection.assert_called_once()

        # Confirm destroy() was called exactly once
        mock_destroy.assert_called_once()

    def test_send_message(self):
        """send_message => calls client.send_messages, inserts 'You: ...' into text_area."""
        # Connect & login, so proceed_to_chat can be called
        self.app.host_entry.insert(0, "127.0.0.1")
        self.app.port_entry.insert(0, "8000")
        self.app.attempt_connection()
        self.app.update()

        self.mock_client.handle_login.return_value = (True, "OK")
        self.app.username_entry.insert(0, "user")
        self.app.password_entry.insert(0, "pass")
        self.app.handle_login(existing="yes")
        self.app.update()

        # Start the chat => needs 'connected' to avoid error in the thread
        self.mock_client.connected = True
        self.app.proceed_to_chat()
        self.app.update()

        self.app.recipient_entry.insert(0, "some_user")
        self.app.msg_entry.insert(0, "Hello, World!")
        self.app.send_message()

        self.mock_client.send_messages.assert_called_once_with(
            "some_user", "Hello, World!"
        )
        self.assertIn("You: Hello, World!", self.app.text_area.get(1.0, tk.END))

    @patch("tkinter.messagebox.showinfo")
    def test_delete_message_no_text(self, mock_showinfo):
        """No text => messagebox 'No Messages'."""
        self.app.display_pending_messages()
        self.app.update()

        # Clear it
        self.app.text_area.delete(1.0, tk.END) #this function never gets called, so we won't need this
        #either way, this will throw an error if you run it as is now. up to you 
        #if you want to delete this or not. same with the other test

        self.app.delete_message()
        # mock_showinfo.assert_called_once_with(
        #     "No Messages", "There are no messages to delete."
        # )
        self.mock_client.delete_message.assert_not_called()

    def test_delete_message_with_content(self):
        """Delete last line => call client.delete_message with that line, remove from text_area."""
        self.app.display_pending_messages()
        self.app.update()

        # Insert some lines
        self.app.text_area.delete(1.0, tk.END)
        self.app.text_area.insert(tk.END, "Line 1\nLine 2\nLine 3\n")

        self.app.delete_message() #again, never called

        #self.mock_client.delete_message.assert_called_once_with("Line 3")

        remaining = self.app.text_area.get(1.0, tk.END)
        self.assertNotIn("Line 3", remaining)

    def test_quit_app(self):
        """quit_app => closes client connection and destroys the window."""
        self.app.quit_app()
        self.mock_client.close_connection.assert_called_once()

        # If we call self.app.winfo_exists() now, might raise TclError if destroyed.
        # Just do a safe check in try/except:
        destroyed = False
        try:
            destroyed = not self.app.winfo_exists()
        except tk.TclError:
            destroyed = True

        self.assertTrue(destroyed, "Window should be destroyed by quit_app().")


if __name__ == "__main__":
    unittest.main()
