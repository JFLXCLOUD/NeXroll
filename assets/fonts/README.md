# Bundled typefaces

These ship with NeXroll so the Preroll Generator offers the same set of faces on
every install. Without them the picker can only list what the host happens to
have: a Windows box shows Arial/Georgia/Impact and friends, while the Docker
image ships nothing but DejaVu and Liberation. Bundling closes that gap, and it
matters more than usual here because Coming Soon lists are re-rendered headlessly
by FFmpeg after every sync — whatever face is chosen has to exist on the server,
not just in the browser.

The selection leans toward the kind of type a preroll actually wants: condensed
display faces for titles, a couple of serifs with some drama in them, and one
monospace. Users can still upload their own via the Generator.

Every file is licensed under the **SIL Open Font License 1.1**, which permits
redistribution as part of a larger work. Full license text for each family is in
`licenses/`, named after the family it covers.

| File | Family | Role | Upstream |
| --- | --- | --- | --- |
| `BebasNeue-Regular.ttf` | Bebas Neue | Condensed display caps | Dharma Type |
| `Anton-Regular.ttf` | Anton | Heavy condensed display | The Anton Project Authors |
| `ArchivoBlack-Regular.ttf` | Archivo Black | Heavy grotesque display | Omnibus-Type |
| `Oswald-Variable.ttf` | Oswald | Condensed gothic sans | The Oswald Project Authors |
| `RobotoCondensed-Variable.ttf` | Roboto Condensed | Condensed sans | The Roboto Project Authors |
| `Cinzel-Variable.ttf` | Cinzel | Roman inscriptional serif | NDISCOVER |
| `PlayfairDisplay-Variable.ttf` | Playfair Display | High-contrast display serif | The Playfair Display Project Authors |
| `Lora-Variable.ttf` | Lora | Text serif | Cyreal |
| `JetBrainsMono-Variable.ttf` | JetBrains Mono | Monospace | JetBrains |

Files marked `-Variable` are variable fonts. FFmpeg's `drawtext` renders them at
their default named instance, and browsers do the same through `@font-face`, so
both halves of the generator agree — this was verified per-file rather than
assumed, since a font that silently renders nothing would be invisible until
someone shipped a blank preroll.

Sourced from the [Google Fonts](https://github.com/google/fonts) repository
(`ofl/` tree). To update one, replace the file and its license side by side.
