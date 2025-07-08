# Actual Code

![alt text](https://api.actualcode.org/uploads/actualcode_horizontal.png)

**Actual Code** is an AI-powered CLI coding agent designed to help you build, test, and deploy programs for real-world hardware projects—no matter your programming skill level.

Whether you're a scientist, engineer, hobbyist, or educator, Actual Code can guide you through wiring, coding, configuration, and troubleshooting for platforms like Raspberry Pi, Arduino, and other microcontrollers. It automates much of the tedious work by reading datasheets, searching for documentation, and generating runnable code tailored to your project.

---

## Features

- **AI Assistant for Hardware Projects:** Communicate with the agent in plain text via the terminal.  
- **Photo & Video Request:** The agent can ask you to take pictures or videos of your hardware setup to analyze wiring or troubleshoot.
- **Automatic Documentation Search:** Before writing any code, Actual Code searches for and reads datasheets, manuals, and documentation for the exact components you're using, ensuring code is up-to-date and accurate.
- **Bash Integration:** The agent can install packages, download files, and run commands in your project environment.
- **Code Generation & Editing:** Uses a text editor tool to write, edit, and fix code files within your project workspace.
- **Workspace-Centric:** All data, code, and multimedia are stored and organized in your chosen project directory.

---

## How to Use

1. **Clone This Repository**

   ```bash
   git clone https://github.com/yourusername/actual-code.git
   cd actual-code
   ```

2. **Install Requirements**

   ```bash
   pip install -r requirements.txt
   ```

   > **Tip:**  
   If you plan to use Python for your hardware project, it's best to run Actual Code and your project **in the same Python environment** (such as a virtualenv or venv).  
   This way, any packages installed by the agent will be available for both development and testing—making your workflow much smoother and fully automated.

3. **Set Up API Keys**

   Create a `.env` file in your project root and add your API keys:

   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ACTUALCODE_API_KEY=your_actualcode_api_key_here
   ```

   ACTUALCODE_API_KEY can be made in https://actualcode.org along with the link to download mobile app.

4. **Run the CLI Agent**

   Use the following command to start Actual Code in CLI mode, specifying your project folder as the workspace directory:

   ```bash
   python cli.py -d {workspace_directory}
   ```

   - The workspace directory is your main hardware project folder.
   - All conversation data, uploaded images/videos, code files, and documentation downloads will be stored here.
   - If the directory does not exist, it will be automatically created.

   **Example:**

   ```bash
   python cli.py -d /home/raspberrypi/dev/stepper_motor
   ```

---

## Example Workflow

- The agent may prompt you to take a picture of your circuit or wiring using your phone.
- It can request a video to check motor movement or other dynamic hardware behaviors.
- It will search for the latest datasheets, read them, and generate accurate code based on your hardware.
- The agent will write and edit files directly in your workspace, and install any dependencies as needed.
- All instructions and help are provided through the terminal in a friendly, step-by-step manner.

---

## License

MIT License (see `LICENSE.md` file for details)

---

## Contributions

PRs, issues, and feedback are always welcome!

---
