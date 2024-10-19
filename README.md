
# Fourth Gen

Fourth Gen is a Python-based tool designed to enhance software development by automating code generation, testing, and integration with OpenAI's language models. This tool facilitates the use of large language models (LLMs) to generate, review, and test Python code dynamically.

## Features

- **Dynamic Code Generation**: Automatically writes Python code based on function specifications.
- **Automated Testing**: Generates and runs unit tests for Python functions.
- **Intelligent Code Reviews**: Uses AI to suggest code improvements and best practices.
- **Flexible Integration**: Adapts to both simple scripts and complex systems seamlessly.

## Installation

Clone this repository, then install the required packages:

```bash
git clone https://github.com/your-repo/fourth_gen.git
cd fourth_gen
pip install -r requirements.txt
```

### Basic Usage

Here's how to instantiate a `CodingAssistant` and use it to generate and review code:

```python
import fourth_gen
import openai

client = openai.OpenAI()
g4 = fourth_gen.CodingAssistant(client)

@g4
def example_function(x, y):
    """
    Adds two numbers.
    """

# Now you can call the newly implemented function
result = implemented_function(5, 3)
```

### Running Unit Tests

You can also generate and run unit tests automatically:

```python
# Generate a unit test for the example_function
test_example_function = assistant.write_unit_test(example_function)

# run the unit test
test_example_function()
```

## Advanced Usage

By default, `fourth_gen` automatically chooses between one of two styles:

1. Generates the Python code for the function once, then uses that ever after.
2. Returns a function which calls the LLM with every invocation.

This decision itself is made by an LLM, based on whether or not it thinks the
function can actually be implemented in Python or if it needs to leverage an
LLM to work. For example, if the requirement is vague or involves natural
language processing, using the LLM is more appropriate.

You can force which approach to use with `.implemnt()` and `.handle()`:

```python
# always use an LLM to handle the task
@g4.handle
def color_to_hex(color_name: str) -> str:
    """
    Return the hex code for this color as a string. Always
    return a hex code in this format: "#0F0F0F". If the color name
    isn't recognized, choose a color which matches the emotional
    vibes of the name.
    """

# always generate a Python implementation
@g4.implement
def fibonacci(n: int) -> int:
    """A highly performant fibonacci function capable of handling large numbers."""
```

The `CodingAssistant` also keeps track of its API usage metrics for a given session:

```python
g4.usage
```

    {'requests': 19,
     'duration': 28.493656635284424,
     'output_tokens': 1068,
     'input_tokens': 4213,
     'cost': 0.016303500000000002}

Finally, you can always just `.chat()` with the `CodingAssistant` (which has
a session history) or use `.task()` to ask it to do an isolated, one-time
task (which neither loads nor adds to session history.)


## License

This project is licensed under the MIT License - see the LICENSE file for details.

