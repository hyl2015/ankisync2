import peewee as pv
from playhouse import signals, sqlite_ext

from time import time
import json
import shortuuid

from ..fields import JSONField

database = sqlite_ext.SqliteExtDatabase(None)


class BaseModel(signals.Model):
    class Meta:
        database = database


class Cards(BaseModel):
    """
    -- Cards are what you review.
    -- There can be multiple cards for each note, as determined by the Template.
    CREATE TABLE cards (
        id              integer primary key,
        -- the epoch milliseconds of when the card was created
        nid             integer not null,--
        -- notes.id
        did             integer not null,
        -- deck id (available in col table)
        ord             integer not null,
        -- ordinal : identifies which of the card templates it corresponds to
        --   valid values are from 0 to num templates - 1
        mod             integer not null,
        -- modificaton time as epoch seconds
        usn             integer not null,
        -- update sequence number : used to figure out diffs when syncing.
        --   value of -1 indicates changes that need to be pushed to server.
        --   usn < server usn indicates changes that need to be pulled from server.
        type            integer not null,
        -- 0=new, 1=learning, 2=due, 3=filtered
        queue           integer not null,
        -- -3=sched buried, -2=user buried, -1=suspended,
        -- 0=new, 1=learning, 2=due (as for type)
        -- 3=in learning, next rev in at least a day after the previous review
        due             integer not null,
        -- Due is used differently for different card types:
        --   new: note id or random int
        --   due: integer day, relative to the collection's creation time
        --   learning: integer timestamp
        ivl             integer not null,
        -- interval (used in SRS algorithm). Negative = seconds, positive = days
        factor          integer not null,
        -- factor (used in SRS algorithm)
        reps            integer not null,
        -- number of reviews
        lapses          integer not null,
        -- the number of times the card went from a "was answered correctly"
        --   to "was answered incorrectly" state
        left            integer not null,
        -- of the form a*1000+b, with:
        -- b the number of reps left till graduation
        -- a the number of reps left today
        odue            integer not null,
        -- original due: only used when the card is currently in filtered deck
        odid            integer not null,
        -- original did: only used when the card is currently in filtered deck
        flags           integer not null,
        -- currently unused
        data            text not null
        -- currently unused
    );
    """

    # Use auto-increment instead of time in Epoch seconds to ensure uniqueness
    id = pv.AutoField()
    nid = pv.ForeignKeyField(Notes, column_name="nid", null=True)
    did = pv.ForeignKeyField(Decks, column_name="did", null=True)
    ord = pv.IntegerField()
    mod = pv.IntegerField()  # autogenerated
    usn = pv.IntegerField(default=-1)
    type = pv.IntegerField(default=0)
    queue = pv.IntegerField(default=0)
    due = pv.IntegerField()  # autogenerated
    ivl = pv.IntegerField(default=0)
    factor = pv.IntegerField(default=0)
    reps = pv.IntegerField(default=0)
    lapses = pv.IntegerField(default=0)
    left = pv.IntegerField(default=0)
    odue = pv.IntegerField(default=0)
    odid = pv.IntegerField(default=0)
    flags = pv.IntegerField(default=0)
    data = pv.TextField(default="")

    class Meta:
        indexes = [
            pv.SQL("CREATE INDEX ix_cards_usn on cards (usn)"),
            pv.SQL("CREATE INDEX ix_cards_nid on cards (nid)"),
            pv.SQL("CREATE INDEX ix_cards_sched on cards (did, queue, due)"),
        ]


@signals.pre_save(sender=Cards)
def cards_pre_save(model_class, instance, created):
    instance.mod = int(time())
    if instance.due is None:
        instance.due = instance.nid


class Col(BaseModel):
    """
    -- col contains a single row that holds various information about the collection
    CREATE TABLE col (
        id              integer primary key,
        -- arbitrary number since there is only one row
        crt             integer not null,
        -- created timestamp
        mod             integer not null,
        -- last modified in milliseconds
        scm             integer not null,
        -- schema mod time: time when "schema" was modified.
        --   If server scm is different from the client scm a full-sync is required
        ver             integer not null,
        -- version
        dty             integer not null,
        -- dirty: unused, set to 0
        usn             integer not null,
        -- update sequence number: used for finding diffs when syncing.
        --   See usn in cards table for more details.
        ls              integer not null,
        -- "last sync time"
        conf            text not null,
        -- json object containing configuration options that are synced
        models          text not null,
        -- json array of json objects containing the models (aka Note types)
        decks           text not null,
        -- json array of json objects containing the deck
        dconf           text not null,
        -- json array of json objects containing the deck options
        tags            text not null
        -- a cache of tags used in the collection (This list is displayed in the browser. Potentially at other place)
    );
    """

    id = pv.IntegerField(primary_key=True, default=1)
    crt = pv.IntegerField(default=lambda: int(time()))
    mod = pv.IntegerField()  # autogenerated
    scm = pv.IntegerField(default=lambda: int(time() * 1000))
    ver = pv.IntegerField(default=11)
    dty = pv.IntegerField(default=0)
    usn = pv.IntegerField(default=0)
    ls = pv.IntegerField(default=0)
    conf = JSONField(null=True)
    # Please create with dict[str(id)]ankisync2.builder.default.Model
    models = JSONField(default=dict)
    # Please create with dict[str(id)]ankisync2.builder.default.Deck
    decks = JSONField(default=dict)
    dconf = JSONField(default=DConf)
    tags = JSONField(default=dict)


@signals.pre_save(sender=Col)
def col_pre_save(model_class, instance, created):
    instance.mod = int(time())