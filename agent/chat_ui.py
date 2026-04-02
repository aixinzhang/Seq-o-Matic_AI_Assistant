"""
Seq-o-Matic AI Assistant -- Chat UI

A Tkinter-based chat interface with logo, message history,
and save/clear functionality.

Usage:
    python chat_ui.py
"""

import tkinter as tk
from tkinter import scrolledtext, END
import threading
import os

from PIL import Image, ImageTk

from agents import software_agent, hardware_agent, clear_history, save_last_qa
from orchestrator import classify


class ChatUI:
    """Chat interface for the Seq-o-Matic AI assistant."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Seq-o-Matic AI Assistant")
        self.root.geometry("750x850")
        self.root.configure(bg="#f0f0f0")
        self.root.resizable(True, True)

        self._build_ui()
        self._bind_keys()

    def _build_ui(self):
        """Create all UI elements."""

        # --- Logo (top center) ---
        logo_frame = tk.Frame(self.root, bg="#f0f0f0")
        logo_frame.pack(pady=10)

        logo_path = os.path.join(os.path.dirname(__file__), "..", "project_logo.png")
        if os.path.exists(logo_path):
            img = Image.open(logo_path)
            # Resize to reasonable height, keep aspect ratio
            max_height = 100
            ratio = max_height / img.height
            new_size = (int(img.width * ratio), max_height)
            img = img.resize(new_size, Image.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(img)
            logo_label = tk.Label(logo_frame, image=self.logo_image, bg="#f0f0f0")
            logo_label.pack()

        title_label = tk.Label(
            logo_frame, text="Seq-o-Matic AI Assistant",
            font=("Arial", 16, "bold"), bg="#f0f0f0", fg="#333333"
        )
        title_label.pack(pady=(5, 0))

        subtitle_label = tk.Label(
            logo_frame, text="Ask about hardware, software, or troubleshooting",
            font=("Arial", 10), bg="#f0f0f0", fg="#666666"
        )
        subtitle_label.pack()

        # --- Chat display area ---
        chat_frame = tk.Frame(self.root, bg="#f0f0f0")
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 5))

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, wrap=tk.WORD, font=("Consolas", 10),
            bg="#ffffff", fg="#333333", relief="flat", borderwidth=1,
            state=tk.DISABLED, spacing3=5,
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for colored messages
        self.chat_display.tag_config("user", foreground="#1a73e8", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("assistant", foreground="#333333", font=("Consolas", 10))
        self.chat_display.tag_config("system", foreground="#888888", font=("Consolas", 9, "italic"))
        self.chat_display.tag_config("category", foreground="#e67e22", font=("Consolas", 9))

        # --- Input area ---
        input_frame = tk.Frame(self.root, bg="#f0f0f0")
        input_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        self.input_field = tk.Entry(
            input_frame, font=("Arial", 12), relief="solid", borderwidth=1,
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        self.input_field.focus()

        send_btn = tk.Button(
            input_frame, text="Send", command=self._on_send,
            font=("Arial", 11, "bold"), bg="#1a73e8", fg="white",
            relief="flat", padx=20, pady=8, cursor="hand2",
        )
        send_btn.pack(side=tk.LEFT, padx=(8, 0))

        # --- Button bar ---
        btn_frame = tk.Frame(self.root, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        save_btn = tk.Button(
            btn_frame, text="Save Last Q&A", command=self._on_save,
            font=("Arial", 9), bg="#27ae60", fg="white",
            relief="flat", padx=12, pady=4, cursor="hand2",
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 5))

        clear_btn = tk.Button(
            btn_frame, text="Clear Memory", command=self._on_clear,
            font=("Arial", 9), bg="#e74c3c", fg="white",
            relief="flat", padx=12, pady=4, cursor="hand2",
        )
        clear_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Status label
        self.status_label = tk.Label(
            btn_frame, text="Ready", font=("Arial", 9),
            bg="#f0f0f0", fg="#888888",
        )
        self.status_label.pack(side=tk.RIGHT)

    def _bind_keys(self):
        """Bind keyboard shortcuts."""
        self.root.bind("<Return>", lambda e: self._on_send())

    def _append_message(self, sender, text, tag="assistant"):
        """Add a message to the chat display."""
        self.chat_display.config(state=tk.NORMAL)
        if sender:
            self.chat_display.insert(END, f"{sender}: ", tag)
        self.chat_display.insert(END, f"{text}\n\n", tag)
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(END)

    def _on_send(self):
        """Handle send button click."""
        question = self.input_field.get().strip()
        if not question:
            return

        self.input_field.delete(0, END)
        self._append_message("You", question, "user")

        # Show thinking status
        self.status_label.config(text="Thinking...", fg="#e67e22")
        self.root.update()

        # Run in background thread to keep UI responsive
        thread = threading.Thread(target=self._process_question, args=(question,))
        thread.start()

    def _process_question(self, question):
        """Process a question in a background thread."""
        try:
            category = classify(question)
            self.root.after(0, self._append_message, "", f"[{category}]", "category")

            if category == "hardware":
                answer = hardware_agent(question)
            elif category == "software":
                answer = software_agent(question)
            elif category == "both":
                hw = hardware_agent(question)
                sw = software_agent(question)
                answer = f"Hardware perspective:\n{hw}\n\nSoftware perspective:\n{sw}"
            else:
                answer = software_agent(question)

            self.root.after(0, self._append_message, "Assistant", answer, "assistant")
            self.root.after(0, self.status_label.config, {"text": "Ready", "fg": "#888888"})

        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "auth" in error_msg.lower():
                error_msg = "API key not set. Set ANTHROPIC_API_KEY environment variable first."
            self.root.after(0, self._append_message, "Error", error_msg, "system")
            self.root.after(0, self.status_label.config, {"text": "Error", "fg": "#e74c3c"})

    def _on_save(self):
        """Save the last Q&A to knowledge base."""
        save_last_qa()
        self._append_message("", "Last Q&A saved to knowledge base", "system")

    def _on_clear(self):
        """Clear conversation memory."""
        clear_history()
        self._append_message("", "Conversation memory cleared", "system")

    def run(self):
        """Start the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = ChatUI()
    app.run()
