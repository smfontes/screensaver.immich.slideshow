# screensaver.immich.slideshow

## Kodi Screensaver that displays a slideshow of pictures from immich.

This Program uses the immich api to retrieve images from immich.
Pictures are selected from immich that were all taken on the same date.
A group of pictures from that date are displayed.
Another date is chosen, and another group of pictures are displayed, etc.
It is kind of like 'memories', except that it chooses random dates, not
dates from previous years that are the same date as today.

### Additional features:

1. You can choose to have some information from each picture displayed on each slide.
    * The image date and time
    * Image tags if they occur in the image file:
        - Headline
        - Caption
        - Sublocation
        - City
        - State/Province
        - Country

        Many of my pictures contain a caption along with a headline. I also add a sublocation to the location information. These two pieces of information are read directly from the image file. Also, if the file has different info than that returned by immich, the file information overrides the information from immich. (Sometimes, the location information that I have added to the file is more accurate than that used by immich)
2. You can choose to have the current time displayed on each slide.
3. You can choose to have information about currently playing music displayed on each slide.
4. Slides can be displayed dimmed.
5. If pictures are taken in "burst mode" with a camera, then you may have dozens of pictures, with multiple occuring in the same second, that look almost identical. This makes for a very boring slideshow if each slide is shown for a few seconds. When there are many pictures taken very close together in time, you can select to have the slideshow speed up for those slides, so that there is much less time  between "burst mode" images. If you choose not to use this feature, then, if there are many slides taken within the same second, only the first and last slides of the group will be shown.