# AstroStudio — Minimum Viable Product (MVP)

AstroStudio is an early working prototype of a visual scientific programming environment designed to make complex Python scientific libraries accessible through an intuitive graphical interface.

This repository **is not the final implementation** of the project. The complete vision is a long-term, team-driven effort. Instead, this MVP demonstrates the core architecture with **real, executable, and tested code**—from Python reflection and automatic node generation to graphical workflow construction, code generation, and execution using **Astropy**.

Every feature marked as implemented in this document has been **actually developed and tested**, not merely planned or mocked.

---

# Implemented Features

| Component                                     | Status                                                                              |
| --------------------------------------------- | ----------------------------------------------------------------------------------- |
| Reflection Engine (`engine/reflection.py`)    | ✅ Fully functional. Automatically extracts metadata from standard Python functions. |
| Library Scanner (`engine/library_scanner.py`) | ✅ Scans entire Python modules and generates `NodeSpec` objects automatically.       |
| Manual Override Layer (`engine/overrides.py`) | ✅ Handles dynamic-signature classes such as `SkyCoord`.                             |
| Graph & Dependency Solver (`engine/graph.py`) | ✅ Real topological sorting with cycle detection.                                    |
| Code Generator (`engine/codegen.py`)          | ✅ Produces readable and executable Python code.                                     |
| Execution Engine (`engine/executor.py`)       | ✅ Supports both direct execution and execution of generated code.                   |
| Visual Node Editor (`gui/node_editor.py`)     | ✅ Interactive node creation and mouse-based connection editing.                     |
| Property Panel (`gui/property_panel.py`)      | ✅ Interactive parameter editing and documentation display.                          |
| Library Panel (`gui/library_panel.py`)        | ✅ Categorized node library with double-click insertion.                             |
| Main Window (`gui/main_window.py`)            | ✅ Complete application layout with Run button and live code preview.                |

---

# Planned Features

The following capabilities are planned for future versions.

### AI Assistant

Natural-language workflow generation.

Example:

> "Load a FITS image, subtract the background, perform photometry, and display the result."

The assistant will automatically generate the corresponding visual workflow.

---

### Live Visualization

Current outputs are displayed in the console only.

Future versions will include:

* FITS image viewer
* Interactive matplotlib rendering
* Real-time plotting
* WCS visualization
* 3D visualization support

---

### Plugin System

Automatic discovery of external libraries through a plugin architecture.

Instead of manually defining nodes, AstroStudio will automatically load plugins from a dedicated `plugins/` directory.

---

### Project Files

Native project format:

```
.astroproj
```

including:

* workflow graph
* node parameters
* execution settings
* custom plugins
* workspace layout

---

### Improved Reflection Engine

Support for:

* `*args`
* `**kwargs`
* decorators
* dynamically generated signatures
* generic typing
* complex object constructors

---

# A Real Engineering Challenge

One interesting issue discovered during development involved Astropy's `SkyCoord`.

Although users normally work with parameters such as:

* ra
* dec
* unit
* frame

the actual constructor signature is:

```python
SkyCoord(*args, copy=True, **kwargs)
```

As a result, Python's standard reflection cannot determine the real parameter list.

The solution was to introduce a small manual registry in:

```
engine/overrides.py
```

This registry defines custom `NodeSpec` objects for dynamic APIs.

The architecture therefore follows a practical strategy:

* **90%** automatic reflection
* **10%** manual overrides for highly dynamic libraries

This approach scales well to many scientific Python ecosystems.

---

# Running AstroStudio

Install dependencies:

```bash
pip install -r requirements.txt
```

Launch the graphical application:

```bash
python -m astrostudio.main
```

Run the core logic example without the GUI:

```bash
python -m astrostudio.examples.example_astropy_coords
```

Example output:

```python
n_node_1 = SkyCoord(
    ra=10.68,
    dec=41.27,
    unit="deg",
    frame="icrs"
)

n_node_2 = to_galactic(coord=n_node_1)
```

Result:

```
<SkyCoord (Galactic):
(l, b) in deg
(121.17057502, -21.57193097)>
```

---

# Adding New Libraries

Most Python libraries can be imported automatically.

Example:

```python
from astrostudio.engine.library_scanner import scan_module

specs = scan_module(
    "scipy.signal",
    max_items=50
)
```

For libraries with dynamic APIs, simply register custom node definitions inside:

```
engine/overrides.py
```

---

# Project Structure

```
astrostudio/
│
├── engine/
│   ├── node.py
│   ├── reflection.py
│   ├── library_scanner.py
│   ├── overrides.py
│   ├── graph.py
│   ├── codegen.py
│   └── executor.py
│
├── gui/
│   ├── node_graphics.py
│   ├── node_editor.py
│   ├── property_panel.py
│   ├── library_panel.py
│   └── main_window.py
│
├── libraries/
│   └── astropy_adapters.py
│
├── examples/
│   └── example_astropy_coords.py
│
└── main.py
```

---

# Running the Unit Tests

Install the test dependencies and run the suite from the repository root:

```bash
pip install -r astrostudio/requirements-dev.txt
pytest --cov=astrostudio --cov-report=term-missing
```

The GUI tests run headlessly; `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`
and shares a single `QApplication` across the session via the `qapp` fixture.

---

# Testing Environment

AstroStudio has been tested in a **headless Qt environment** using:

```
QT_QPA_PLATFORM=offscreen
```

The following components were successfully verified:

* GUI initialization
* Node creation
* Connection drawing
* Automatic code generation
* Workflow execution
* Screenshot generation

A real screenshot (`astrostudio_screenshot.png`) was produced during testing.

On a standard desktop environment, simply run:

```bash
python -m astrostudio.main
```

---

# Project Vision

AstroStudio aims to become a **next-generation visual scientific computing environment** that bridges modern Python ecosystems with an intuitive graphical interface.

The long-term goals include:

* Automatic conversion of Python libraries into visual nodes
* Transparent code generation
* AI-assisted workflow creation
* Plugin-based extensibility
* Live visualization
* Interactive debugging
* Reproducible scientific workflows
* Cross-platform desktop application
* Support for astronomy, physics, data science, engineering, and education

Rather than hiding Python, AstroStudio exposes it in a transparent and educational way—allowing users to understand, modify, and export the generated code while benefiting from the simplicity of visual programming.
