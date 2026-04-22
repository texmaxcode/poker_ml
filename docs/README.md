# Documentation

| Document | Contents |
| -------- | -------- |
| [improvements.md](improvements.md) | Test coverage gaps, UI/engine suggestions, timer and HUD behavior |
| [data-and-sqlite.md](data-and-sqlite.md) | Database paths, schema, **`texas-holdem-parquet-export`**, Parquet layout, notebook exploration |

**Coverage:** run **`texas-holdem-gym-test`** (or **`coverage run -m pytest`** then **`coverage report`**) so **`fail_under`** / **`omit`** in root **`pyproject.toml`** apply; see root **[README.md — Tests](../README.md#tests)**.

| Notebook | Contents |
| -------- | -------- |
| [notebooks/hand_history_exploration.ipynb](../notebooks/hand_history_exploration.ipynb) | Example pandas / matplotlib exploration on exported Parquet |

Project overview and how to run the app: [README.md](../README.md).
