# Fourth Gen

The dream of fourth generation programming languages was to have a programming language
that felt more like natural language and were thus simultaneously powerful and flexible
than third generation languages, while being so easy to use that even non-programmers
could use them. In brief, the computer on Star Trek.

`fourth_gen` is a Python package that makes that dream a reality. Now, thanks to the
power of LLMs, you can specify function behavior in plain English, without ever having
to write a single line of code. Not only that, but the generated code is capable of
handling novel or unexpected cases, by delegating to LLMs as needed to cover cases which
are too vague or require too much judgement to implement as a rigid algorithm.

This paradigm allows the rapid development of powerful programs that combine
the performance of traditional computing paradigms with the flexibility of LLMs.

## Installation

Clone this repository, then install the required packages:

```bash
git clone https://github.com/your-repo/fourth_gen.git
cd fourth_gen
pip install -r requirements.txt
```

## Basic Usage

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

## Advanced Usage

### Rigid vs. Flexible Approach

By default, `fourth_gen` automatically chooses between one of two styles:

1. Generates the Python code for the function once, then uses that ever after.
2. Returns a function which calls the LLM with every invocation.

This decision itself is made by an LLM, based on whether or not it thinks the
function can actually be implemented in Python or if it needs to leverage an
LLM to work. For example, if the requirement is vague or involves natural
language processing, using the LLM is more appropriate.

You can force which approach to use with `@implement` and `@handle`. If
you want the LLM to handle every function call on a case-by-case basis, you
can use `@handle`:

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
```

On the other hand, if you want it to call the LLM only once, to generate Python
code for the function, then use that Python code every time the function is
called from then on, you can use `@implement`:
```python
@g4.implement
def fibonacci(n: int) -> int:
    """A highly performant fibonacci function capable of handling large numbers."""
```

If you want it to automatically decide which of the above approaches to use,
then just use `@write`:


```python
@g4.write
def fibonacci(n: int) -> int:
    """A highly performant fibonacci function capable of handling large numbers."""
```

The `fourth_gen.CodingAssistant` can also wrap an existing function to handle
exceptions. The function is called normally, and if it returns a value then 
that's that; the LLM is not called. However, if the function throws an exception,
then the LLM will be shown the function, its arguments, and the error message from
the exception and will be tasked with trying to guess what the "correct" return value
should be, and that is returned instead. In other words, it implements the language
feature that programmers have long wished for: "Do what I mean, not what I say."

### Error Handling

```python
@g4.handle_error
def database_capital_lookup(state: str) -> str:
    """returns the name of the capital of the given US state."""
    raise ValueError(f"State {state!r} not found in database table 'state'")

capital_of("Wsiconisn")
```

    'Madison'

Finally, to have it both implement the function and handle errors, you can
simply use the `fourth_gen.CodingAssistant` itself as a high-level, all-in-one
decorator:

```python
@g4
def fibonacci(n: int) -> int:
    """A highly performant fibonacci function capable of handling large numbers."""
```

This is equivalent to stacking the `@handle_error` and `@write` decorators:

```python
@g4.handle_error
@g4.write
def fibonacci(n: int) -> int:
    """A highly performant fibonacci function capable of handling large numbers."""
```

### Interactive Usage

Finally, you can always just `.chat()` with the `CodingAssistant` (which has
a session history) or use `.task()` to ask it to do an isolated, one-time
task (which neither loads nor adds to session history.) These features can
be used interactively during development, or used in the program itself:

```python
[ g4.task(f"Is this tweet rude? {tweet!r}") for tweet in twitter_feed ]
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

This is mainly useful for keeping an eye on how much of a bill you're racking
up with all this LLM magic.


## License

This project is licensed under the MIT License - see the LICENSE file for details.

