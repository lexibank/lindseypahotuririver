import shutil
import pathlib
import itertools
import subprocess

import attr
from clldutils.path import md5
import pylexibank
import gdown
from collabutils.googlesheets import Spreadsheet


@attr.s
class Lexeme(pylexibank.Lexeme):
    Audio_Files = attr.ib(
        default=None,
        metadata=dict(
            separator=' ',
            propertyUrl="http://cldf.clld.org/v1.0/terms.rdf#mediaReference"),
    )


class Dataset(pylexibank.Dataset):
    dir = pathlib.Path(__file__).parent
    id = "lindseypahotuririver"

    lexeme_class = Lexeme

    # define the way in which forms should be handled
    form_spec = pylexibank.FormSpec(
        brackets={"(": ")"},  # characters that function as brackets
        separators=";/,",  # characters that split forms e.g. "a, b".
        missing_data=('?', '-'),  # characters that denote missing data.
        strip_inside_brackets=True   # do you want data removed in brackets or not?
    )

    def cmd_download(self, args):
        document = Spreadsheet('1AWx_sgsYy6tedegqeoXQMpVHK8HKNbQ2ObZTbkLG1bE')
        document.fetch_sheets(
            sheets={'Transcriptions': 'transcriptions.csv'},
            outdir=self.raw_dir,
        )
        for row in self.raw_dir.read_csv('transcriptions.csv', dicts=True):
            output = self.raw_dir / 'audio' / row['File name']
            if not output.exists() and row['Audio link']:
                fid = row['Audio link'].split('file/d/')[1].split('/view?')[0]
                gdown.download(id=fid, output=str(output))
        for p in self.raw_dir.joinpath('audio').glob('*.wav'):
            #subprocess.check_call(['lame', '--preset', 'insane', str(p), p.parent / '{}.mp3'.format(p.stem)])
            subprocess.check_call(['lame', '--preset', 'medium', str(p), p.parent / '{}.mp3'.format(p.stem)])

    def cmd_makecldf(self, args):
        args.writer.cldf.add_component('MediaTable')

        audio_dir = self.cldf_dir / 'audio'
        if not audio_dir.exists():
            audio_dir.mkdir()
        audio_files = set()

        args.writer.add_languages()

        for gloss, rows in itertools.groupby(
            sorted(self.raw_dir.read_csv('transcriptions.csv', dicts=True), key=lambda r: r['Gloss']),
            lambda r: r['Gloss'],
        ):
            args.writer.add_concept(
                ID=gloss,
                Name=gloss.replace('-', ' '),
            )
            for row in rows:
                audio_id = None
                audio = self.raw_dir / 'audio' / row['File name'].replace('.wav', '.mp3')
                if row['File name'] and audio.exists():
                    audio_id = md5(audio)
                    target_path = audio_dir / '{}.wav'.format(audio_id)
                    if not target_path.exists():
                        shutil.copy(audio, target_path)
                    if audio_id not in audio_files:
                        args.writer.objects['MediaTable'].append(dict(
                            ID=audio_id,
                            Media_Type='audio/wav',
                            Download_URL='audio/{}'.format(target_path.name),
                        ))
                        audio_files.add(audio_id)
                lex = args.writer.add_form(
                    Language_ID=row['Language'],
                    Parameter_ID=gloss,
                    Value=row['Transcription'],
                    Form=row['Transcription'],
                    Audio_Files=[audio_id] if audio_id else [],
                    #Source=[row['Source']],
                )
