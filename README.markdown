# Deckset Inline

Include content from other files in your Deckset slides.

## Okay how?

First install the tool:

```bash
pip install deckset-inline
```

Then prepare a file from which you want to include some content. This is `a_file.py`:

```python
print("Hello I am a text file, but this line is not interesting.")
print("This second line, though, is vital for any presentation.")
print("This third line should be included too.")
print("But not this fourth one, don't care for this one.")
```

Then add an opening `inline` *directive* and a closing `inline` *directive* to your presentation Markdown file, where you want the content to appear:

```markdown
<!-- <inline src="a_file.py" verbatim lang="python" start="2" end="3"> -->
<!-- </inline> -->
```

Then run the tool with your presentation file:

```bash
deckset-inline --in-place --backup-ext bak slides.md
```

See how your file has been modified *in-place*, and you now have the lines 2 to 3 of `a_file.py` included between the directives:

````markdown
<!-- <inline src="a_file.py" verbatim lang="python" start="2" end="3"> -->
```python
print("This second line, though, is vital for any presentation.")
print("This third line should be included too.")
```
<!-- </inline> -->
````

See how the directives stay? You can now run the command again after you change the source files.

## I see, but why?

I want to test the code that I put in my slides, so I write it in proper code files that I then run and test (Yes, I sometimes write tests for the code in my slides). If I find an issue with the code, I don't want to be copy-pasting code into the slides again. This tools takes care of that for me.

## Okay, I want this, tell me more

Welcome!

Directives are one line HTML comments with a home made tag inside. The basic directive has the tag name `inline` and these are the available attributes:

 * `src`: The only mandatory attribute, it specifies the path of the file to include.
 * `verbatim`: A flag. When present (it takes no value), the included code will be surrounded by lines with 3 backtics each ` ``` `
 * `lang`: Implies `verbatim`. Specifies the language that will appear at the top of the backticks block.
 * `start`: The *first* line of the source file (counted starting at 1) that will appear in the block.
 * `end`: The *last* line of the source file (counted starting at 1) that will appear in the block.

For convenience, I've added a second directive called `python`, which is equivalent of setting `lang="python"` on an `inline` directive.

The tool puts its output on stdout by default, like `sed` does, only if you pass the `-i` (`--in-place`) flag it will modify the original file. I recommend you also use the `-b` (`--backup-ext`) flag to force the creation of a backup of your file, if you aren't using version control for your slides.

There is also an option (`-c` or `--clean`) which deletes all the content between opening and closing directives, while leaving the directives themselves intact.

## Any caveats?

* The inline operation is not recursive, and the tool will not handle well if you include files that contain other directives.
* The parsing is quite rudimentary and line based, so directives cannot span across multiple lines.
