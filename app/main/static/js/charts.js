/* charts.js */

morris = null;
top_lbl='$';
bDrawTopLabel = true;

//-------------------------------------------------------------------------------
function drawMorrisBarChart(id, data, xkey, ykeys, options, ext_options=null) {
    /* Wrapper for morris.js bar chart w/ default stylings.
    */

    if(!morris) {
        morris = window.morris = {};
        morris = Object.create(Morris);
        initLabelTopExt();
    };

    // Defaults
    var _options = {
        element: id, // graph container selector id
        data: data, // series data
        xkey: xkey, // key for x-axis data
        ykeys: ykeys, // keys (list) for y-axis data
        labels: ['Residential', 'Business'], // labels for ykeys -- will be displayed when you hover over the chart
        labelTop: true, // custom extension
        axes: true, // false for none, 'x' for x-axis, 'y' for y-axis
        grid: false,
        hideHover: 'auto',
        hoverCallback: null, // replace w/ custom function
        barColors: ['#279bbe', '#ec8380'], // red, blue
        gridTextColor: ['#6a6c6f'],
        gridTextSize: 14,
        gridTextWeight: 300,
        padding: 15,
        barSizeRatio: .80,
        barWidth: 25,
        stacked:false,
        resize: true
    };

    // Override defaults
    for(var k in options) {
        if(_options.hasOwnProperty(k))
            _options[k] = options[k];
        else
            console.log(format("unknown option '%s':'%s'",k,options[k]));
    }

    var barChart = new Morris.Bar(_options);

    $('svg').css('overflow','visible');
    $('svg').css('top','-20px');

    return barChart;
}

//-------------------------------------------------------------------------------
function initLabelTopExt() {
    /* Morris.js extension allowing for y-axis value on bar graphs to display
    */

    morris.Bar.prototype.defaults["labelTop"] = false;

    // Label render
    morris.Bar.prototype.drawLabelTop = function(xPos, yPos, text){
        var label;
        text = top_lbl + text;
        return label = this.raphael.text(xPos, yPos, text)
            .attr('font-size', this.options.gridTextSize)
            .attr('font-family', this.options.gridTextFamily)
            .attr('font-weight', this.options.gridTextWeight)
            .attr('fill', this.options.gridTextColor);
    };

    morris.Bar.prototype.drawSeries = function() {

        var barWidth, bottom, groupWidth, idx, lastTop, left, leftPadding, numBars,
            row, sidx, size, spaceLeft, top, ypos, zeroPos;
        groupWidth = this.width / this.options.data.length;
        numBars = this.options.stacked ? 1 : this.options.ykeys.length;
        barWidth = (groupWidth * this.options.barSizeRatio - this.options.barGap * (numBars - 1)) / numBars;

        if (this.options.barSize) {
            barWidth = Math.min(barWidth, this.options.barSize);
        }

        // Create test top label. See if width too large to fit.
        var lblWidth = this.raphael.text(-10000,-10000,'$111').getBBox()['width'].toFixed(2);
        if(Number(lblWidth) > Number(barWidth).toFixed(2)){
            bDrawTopLabel = false;
            //console.log('Hiding top labels. labelWidth > barWidth');
        }
        else {
            //console.log('Showing top labels. labelWidth='+lblWidth+', barWidth='+barWidth.toFixed(2));
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

                            if (this.options.labelTop == true && !this.options.stacked && bDrawTopLabel) {
                                label = this.drawLabelTop(
                                    (left + (barWidth / 2)),
                                    top - 10,
                                    Sugar.Number.abbr(row.y[sidx], 1)
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
