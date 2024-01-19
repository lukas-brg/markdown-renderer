import random, json
from .mdparser import parse_markdown
from .mdparser.htmltree import  SelfClosingTag, HtmlNode, TextNode
from .mdparser.mdparser import make_table_of_contents
from .cards import LearningCard
from .errors import try_read_file
from .config import get_config

config = get_config()




class CardDeck:
    def __init__(self):
        self.cards: list[LearningCard] = []

    def add_card(self, card: LearningCard):
        self.cards.append(card)

    def to_json(self, filepath, include_styles=False):
        with open(filepath, "w") as f:
            f.write(json.dumps([c.to_dict(include_styles) for c in self.cards], indent=2, ensure_ascii=False))
    
    def shuffle(self):
        random.shuffle(self.cards)

    def get_cards_html(self):
        return [c.html for c in self.cards]
    
    def get_text_unparsed(self):
        return [(c.front, c.back) for c in self.cards]



class CardLoader:

    def __init__(self):
        self.html: list[HtmlNode] = []
        self.cards = CardDeck()
  
        self.markdown = []

    

    def add_card(self, card_str):
        card = LearningCard.from_str(card_str)
        self.html.append(card.to_html())
        if tag := config.cardloader.card_separator:
            sep = SelfClosingTag(tag)
            card.html.add_children(sep)

        self.cards.add_card(card)


    def parse_card(self, lines: list[str], start: int):
        
        def check_length():
            if config.cardloader.length_warning and i - start >= config.cardloader.length_warning:
                print(f"Warning: Unusually long card detected (Line {start+1}-{i+1}). Did you maybe forget an {{END}} tag?")

        for i, line in enumerate(lines[start+1:], start+1):
            if line.rstrip() == LearningCard.end_tag:
                card_str = "".join(lines[start:i-1]) # dont include end tag
                self.add_card(card_str)
                return i + 1
            
            if LearningCard.is_card(line):
                check_length()
                card_str = "".join(lines[start:i])
                self.add_card(card_str)
                return i
        
        check_length()

        card_str = "".join(lines[start:])
        self.add_card(card_str)
        return i + 1
    


    def process_footnotes(self, cards_only=False) -> list[HtmlNode]:
        
        if cards_only:
            root_node = HtmlNode("root", *self.cards.get_cards_html())
        else:
            root_node = HtmlNode("root", *self.html)

        refs = root_node.search_by_property("set_class", "footnote-ref")
        footnote_divs = list(root_node.search_by_property("set_class", "footnotes-div"))
        

        for footnote_div in footnote_divs:
            footnote_div.remove_from_tree()

        div_container = HtmlNode("container", *footnote_divs)

        display_div = HtmlNode("div", set_class="footnotes-div")

        for count, fn_ref in enumerate(refs, 1):
            fn_text = fn_ref.properties["id"].replace("ref-", "")
           
            fn_ref.children[0].replace_in_tree(TextNode(f"[{count}]"))
            fn_id = f"footnote-{fn_text}"

            fn = next(div_container.search_by_property("id", fn_id, substring_search=False, find_all=False))
            fn_container = fn.parent.parent
            fn.children[0].replace_in_tree(f"{count}.")
            display_div.add_children(fn_container)

        if display_div.children:
            root_node.add_children(display_div)
      
        return root_node.children




    def get_cards(self, shuffle=False):
        if shuffle:
            self.cards.shuffle()
        
        cards_html = self.process_footnotes(cards_only=True)
        
        if config.document.table_of_contents:
            container = HtmlNode("container", *cards_html)
            toc_div = make_table_of_contents(container, config.document.toc_max_heading)
            doc = toc_div + cards_html
            return doc
        
        return cards_html
    

    def get_markdown(self):
        return self.markdown


    def get_cards_and_markdown(self):
        self.html = self.process_footnotes()
        if config.document.table_of_contents:
            container = HtmlNode("container", *self.html)
            toc_div = make_table_of_contents(container, config.document.toc_max_heading)
            doc = toc_div + self.html 
            return doc
        
        return self.html
       
       

    def parse_file(self, input_file: str):
        
        lines = try_read_file(input_file)
        
        lines = lines.splitlines(True)

        i = 0
        md_string = ""

        while i < len(lines):
            line = lines[i]

            if LearningCard.is_card(line):
                md_elems = parse_markdown(md_string)
                self.markdown.extend(md_elems)
                self.html.extend(md_elems)
                md_string = ""
                i = self.parse_card(lines, i)
            else:
                md_string += line
                i += 1

        md_elems = parse_markdown(md_string)
        self.html.extend(md_elems)
        self.markdown.extend(md_elems)

