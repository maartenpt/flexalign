# Quick start

## 1. Align two TEI witnesses (sentence level)

```bash
flexalign align --pivot witnessA.xml witnessB.xml --output pair-s.json --level s --backend identity
```

Requires compatible `xml:id` (or attribute matching if you use `--backend attribute --attr n`).

## 2. Apply tuids onto the target XML

```bash
flexalign apply pair-s.json --pivot witnessA.xml --project-root . --out-dir aligned/
```

## 3. Plain text → TEI → align

```bash
flexalign plain prepare --input-dir ./raw --out-dir ./tei --level s
flexalign align --pivot ./tei/en.tei.xml ./tei/de.tei.xml --output pair.json --level s
```

Or one step:

```bash
flexalign plain align-pair en.txt de.txt --output pair.json --backend identity --level s
```

## 4. Convert TMX to TEI export

```bash
flexalign convert --from tmx --to teitok --input corpus.tmx --output corpus.xml --lang-src en --lang-tgt de
```

## 5. Inspect backends and sets

```bash
flexalign info backends
flexalign info sets --project-root .
```

## Next

- [Home](Home.md) — full command table.
- [Concepts](Concepts.md) — data shapes.
- [Installation](Installation.md)
