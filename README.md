# 🧱 Iris Properties Merger

**Iris Properties Merger** is an simply advanced tool designed for **shader developers** and **community helpers**.
Its main purpose is to **simplify and automate** the process of adding new blocks and items (from mods or future game versions) to the crucial `block.properties` file, mainly for [Bliss-Shader/X0nk](https://github.com/X0nk/Bliss-Shader).

Forget about manually scanning through hundreds of lines and copying properties by hand —  
this tool will do it **for you**, intelligently and safely!

<img width="1194" height="820" alt="image" src="https://github.com/user-attachments/assets/2de1942d-1655-4cfb-b947-85afa6f974f7" />

## ✨ Key Features

### 🔍 Visual Diff View
Compare the **original** and **modified** versions of your file side by side.  
All newly added lines are **highlighted** for easy review.

### 🤖 Smart Suggestions
Paste a list of new items, and the program will:
- **Analyze** their names
- **Suggest** which existing categories (`block.1`, `block.2`, etc.) they fit best  
- Show a **confidence percentage** for each match

**Recommendation: Use it as last resort.**

### 🧩 Advanced Template Mode
Pick any existing item in the file (e.g., `minecraft:stone_wall`) as a **template**.  
The tool automatically:
- Finds **all variants** (including blockstates)
- Applies your new items to each of those properties  

Perfect for complex blocks like **walls**, **fences**, or **stairs** and forget about adding +30 variant of stairs for one new block!

### ⚙️ Auto-Mapper
Define your own mapping rules in `auto_rules.txt`, e.g.:
[put_txt_file_here_of_example] any item ending with _wall → use template stone_wall
Then, with one click, the program will automatically assign dozens of new items to the proper categories — saving you tons of time.

**Highly recommended.**

### 🕒 Full History with Undo/Redo

Every operation is saved in the history log.
You can undo, redo, or even restore any previous state of the file at any time. **Double click it**

### 🎓 Built-in Interactive Tutorial

Not sure where to start?
Launch the integrated tutorial, which will walk you through all the main features step by step — with real examples and on-screen guidance.

**Recommended to restart program afterward, just in case.**

### 🗂️ Category Management

Easily browse, filter, and sort all categories in your file.
You can also create new ones directly from within the app.

### 🎨 UI Customization

Switch between light and dark themes to suit your personal preference.

### ⚡ How It Works

The workflow is simple and intuitive:
- Load your block.properties file
- Paste a list of new items you want to add
  Choose a method:
  1. Click on one of the suggestions
  2. Use **Template Mode** for complex blocks
  3. Use **Auto-Mapping** for full automation
- Apply changes and view the merged result in the "After (Merged)" window
- Save the finished file under a new name

### 🚀 Getting Started

Download the latest version from the **Releases** section

Run the **.exe** file

Click **Start Tutorial** to quickly learn how to use the tool

---
### Plans for future
In the future, if there is a need and interest, I plan to add the option to add items to other shader files as well, i.e. item.properties
