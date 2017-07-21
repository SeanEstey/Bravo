/* charts.js */

MyMorris = null;

test_data= [
  { date: '2012-02-24', value: 20, count: 20 },
  { date: '2012-05-24', value: 10, count: 10 },
  { date: '2012-06-03', value: 55, count: 55 },
  { date: '2012-06-04', value: 6, count: 6 },
  { date: '2012-06-07', value: 0, count: 0 },
  { date: '2012-06-13', value: 19, count: 19 },
  { date: '2012-06-14', value: 0, count: 0 },
  { date: '2012-06-21', value: 15, count: 15 },
  { date: '2012-06-22', value: 8, count: 8 },
  { date: '2012-06-22', value: 75, count: 75 },
  { date: '2012-07-26', value: 32, count: 32 },
  { date: '2012-08-24', value: 64, count: 64 },
  { date: '2012-08-31', value: 32, count: 32 },
  { date: '2012-09-24', value: 48, count: 48 },
  { date: '2012-11-24', value: 15, count: 15 }
];
x_key='date';
y_keys=['value'];
top_lbl='$';

//-------------------------------------------------------------------------------
function initCharts() {

    $(function() {
        MyMorris = window.MyMorris = {};
        MyMorris = Object.create(Morris);
        initLabelTopExt();
        console.log('Morris initialized w/ LabelTop');

        drawChart('don_chart', test_data, x_key, y_keys);
    });
}

//-------------------------------------------------------------------------------
function drawChart(id, data, xkey, ykeys) {
    /*
    @data: list of {}'s with x_axis labels and y-values
    @labels: labels for the ykeys -- will be displayed when you hover over the chart
    @xkey, @ykeys: name of data record attribute containing x/y-values
    @element: id attr of selector graph drawn in 
    @lineColors: ['#5bc0de', '#5bc0de', '#5bc0de'],
    */

    new Morris.Bar({
        element: id,
        data: data,
        xkey: xkey, 
        ykeys: ykeys,
        labels: ['$'], 
        axes: [],
        grid: false,
        hideHover: 'auto',
        //barColors: ['#0b62a4', '#7a92a3', '#4da74d', '#afd8f8', '#edc240', '#cb4b4b', '#9440ed'],
        barColors: ['#ec8380'],
        //barColors: ['#5bc0e3'],
        gridTextColor: ['#6a6c6f'],
        gridTextSize: 14,
        gridTextWeight: 300,
        padding: 1,
        labelTop: true,
        barSizeRatio: .80,
        barWidth: 25,
        resize: true
    });

    $('svg').css('overflow','visible');
    $('svg').css('top', '1px');
}

//-------------------------------------------------------------------------------
function initLabelTopExt() {
    /* Morris.js extension allowing for y-axis value on bar graphs to display
    */

    MyMorris.Bar.prototype.defaults["labelTop"] = false;

    // Label render
    MyMorris.Bar.prototype.drawLabelTop = function(xPos, yPos, text){
        var label;
        text = top_lbl + text;
        return label = this.raphael.text(xPos, yPos, text)
            .attr('font-size', this.options.gridTextSize)
            .attr('font-family', this.options.gridTextFamily)
            .attr('font-weight', this.options.gridTextWeight)
            .attr('fill', this.options.gridTextColor);
    };

    MyMorris.Bar.prototype.drawSeries = function() {

        var barWidth, bottom, groupWidth, idx, lastTop, left, leftPadding, numBars,
            row, sidx, size, spaceLeft, top, ypos, zeroPos;
        groupWidth = this.width / this.options.data.length;
        numBars = this.options.stacked ? 1 : this.options.ykeys.length;
        barWidth = (groupWidth * this.options.barSizeRatio - this.options.barGap * (numBars - 1)) / numBars;

        if (this.options.barSize) {
            barWidth = Math.min(barWidth, this.options.barSize);
        }

        spaceLeft = groupWidth - barWidth * numBars - this.options.barGap * (numBars - 1);
        leftPadding = spaceLeft / 2;
        zeroPos = this.ymin <= 0 && this.ymax >= 0 ? this.transY(0) : null;

        // Get bars func
        return this.bars = (function() {
            var _i, _len, _ref, _results;
            _ref = this.data;
            _results = [];

            for (idx = _i = 0, _len = _ref.length; _i < _len; idx = ++_i) {
                row = _ref[idx];
                lastTop = 0;

                // Push results func
                _results.push((function() {

                    var _j, _len1, _ref1, _results1;
                    _ref1 = row._y;
                    _results1 = [];

                    // Inner loop
                    for(sidx = _j = 0, _len1 = _ref1.length; _j < _len1; sidx = ++_j) {
                        ypos = _ref1[sidx];

                        if (ypos !== null) {
                            if (zeroPos) {
                                top = Math.min(ypos, zeroPos);
                                bottom = Math.max(ypos, zeroPos);
                            }
                            else {
                                top = ypos;
                                bottom = this.bottom;
                            }

                            left = this.left + idx * groupWidth + leftPadding;

                            if (!this.options.stacked) {
                                left += sidx * (barWidth + this.options.barGap);
                            }

                            size = bottom - top;

                            if(this.options.verticalGridCondition && this.options.verticalGridCondition(row.x)) {
                                this.drawBar(
                                    this.left + idx * groupWidth,
                                    this.top,
                                    groupWidth,
                                    Math.abs(this.top - this.bottom),
                                    this.options.verticalGridColor,
                                    this.options.verticalGridOpacity,
                                    this.options.barRadius,
                                    row.y[sidx]
                                );
                            }

                            if(this.options.stacked) {
                                top -= lastTop;
                            }

                            this.drawBar(
                                left,
                                top,
                                barWidth,
                                size,
                                this.colorFor(row, sidx, 'bar'),
                                this.options.barOpacity,
                                this.options.barRadius
                            );

                            _results1.push(lastTop += size);

                            if (this.options.labelTop && !this.options.stacked) {
                                label = this.drawLabelTop(
                                    (left + (barWidth / 2)),
                                    top - 10,
                                    row.y[sidx]
                                );

                                textBox = label.getBBox();
                                _results.push(textBox);
                            }
                        }
                        else {
                            _results1.push(null);
                        }
                    } // End inner loop

                    return _results1;

            }).call(this)); // End push results func
        }

        return _results;

        }).call(this); // end drawSeries
    };
}
