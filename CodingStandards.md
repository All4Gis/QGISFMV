
What is that? Simply some "rules" that you're not obliged to respect, but improves the *visual*
quality of your python code

So, let's get started.

<!-- MarkdownTOC -->

- [Symbols](#symbols)
    - [Operators](#operators)
    - [Commas and colons](#commas-and-colons)
    - [Calling functions](#calling-functions)
    - [Brackets](#brackets)
    - [Indentation](#indentation)
- [Operators](#operators-1)
- [Names](#names)
    - [Variable And Functions](#variable-and-functions)
    - [Classes](#classes)

<!-- /MarkdownTOC -->

## Symbols

### Operators

```python
# no
if this=='is ugly':
    print('right?')

# yes
if this == 'is beautiful':
    print('right?')

# same for '=', '+', '-', '/', '%', etc
```

### Commas and colons

The commas are a bit special, but natural: no space before, one space after. Same apply for colons.

```python
# no
if 'this' :
    print('is','ugly' , 'right?')
    my_dict = {'key' :"value"}

# yes
if 'this':
    print('is', 'ugly', 'right?')
    my_dict = {'key': "value"}
```

### Calling functions

This is just for when you *call* functions.

```python
# no
this ('is', 'ugly', 'right?')

# yes
this('is', 'beautiful', 'right?')
```

### Brackets

This convention applies for `[]`, `()`, and `{}`: no space after opening bracket or before the 
closing one.

```python
# no
my_tuple = ( 'this', 'is', 'ugly', 'right?' )
my_list = [ 'this', 'is', 'ugly', 'right?' ]

# yes
my_tuple = ('this', 'is', 'beautiful', 'right?')
my_list = ['this', 'is', 'beautiful', 'right?']
```

### Indentation

You python code should be indented with 4 spaces.

*No need for an example here I guess*

## Operators

For booleans (`True`, `False`) and `NoneType` (`None`), you should compare them using the `is` and 
`is not` operators, instead of `!=` and `==`:

```python
# no
if this == True:
    print('is ugly right?')

# yes
if this is True:
    print('is beautiful right?')
```

## Names

### Variable And Functions

In python, you variable names should be written in `snake_case`. Note in `camelCase`, `PascalCase`,
or `I_Do_Not_Know_The_Name_Of_This_One`. Same apply for functions

```python
# no
thisIsUgly == 'right?'
def And_This_Is_Too():
    return True

# yes
this_is_beautiful == 'right?'
def and_this_is_too():
    return True
```

### Classes

The classes you create are different: they should be written in `PascalCase`.

```python
# no
class this_is:

    def __init__(self):
        print('ugly')
        return 'right?'

# yes
class ThisIs:

    def __init__(self):
        print('beautiful')
        return 'right?'
```


That's it for now! If you want more about syntax conventions, you should have a look at the **PEP8** conventions!

Recommended readings

* <a href="https://stackabuse.com/introduction-to-the-python-coding-style/" target="_blank">Introduction to the Python Coding Style</a>
* <a href="https://www.python.org/dev/peps/pep-0008/" target="_blank">PEP 8</a>

And remember **Zen of Python**  

    The Zen of Python, by Tim Peters
    Beautiful is better than ugly.
    Explicit is better than implicit.
    Simple is better than complex.
    Complex is better than complicated.
    Flat is better than nested.
    Sparse is better than dense.
    Readability counts.
    Special cases aren't special enough to break the rules.
    Although practicality beats purity.
    Errors should never pass silently.
    Unless explicitly silenced.
    In the face of ambiguity, refuse the temptation to guess.
    There should be one-- and preferably only one --obvious way to do it.
    Although that way may not be obvious at first unless you're Dutch.
    Now is better than never.
    Although never is often better than *right* now.
    If the implementation is hard to explain, it's a bad idea.
    If the implementation is easy to explain, it may be a good idea.
    Namespaces are one honking great idea -- let's do more of those!
